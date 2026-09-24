import hashlib
import secrets
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import AppError, validation_details
from app.core.logging import log_event
from app.models import RegistrationReceipt
from app.schemas.patient import REQUIRED_FIELDS, PatientCreate, PatientRead, PatientUpdate
from app.services.patients import add_patient, get_patient
from app.voice.contracts import (
    PrepareRegistration,
    ResetRegistration,
    SaveRegistration,
    UpdateRegistration,
)
from app.voice.state import DraftStore

READBACK_LABELS = {
    "first_name": "First name",
    "last_name": "Last name",
    "date_of_birth": "Date of birth",
    "sex": "Sex",
    "phone_number": "Phone number",
    "email": "Email",
    "address_line_1": "Street address",
    "address_line_2": "Apartment or unit",
    "city": "City",
    "state": "State",
    "zip_code": "ZIP code",
    "insurance_provider": "Insurance provider",
    "insurance_member_id": "Insurance member ID",
    "preferred_language": "Preferred language",
    "emergency_contact_name": "Emergency contact name",
    "emergency_contact_phone": "Emergency contact phone",
}


class RegistrationService:
    def __init__(self, store: DraftStore):
        self.store = store

    def execute(self, session: Session, call_id: str, name: str, arguments: dict) -> dict:
        with self.store.lock:
            if name == "update_registration":
                payload = UpdateRegistration.model_validate(arguments)
                return self.update(call_id, payload.fields)
            if name == "prepare_registration":
                PrepareRegistration.model_validate(arguments)
                return self.prepare(call_id)
            if name == "save_registration":
                payload = SaveRegistration.model_validate(arguments)
                return self.save(session, call_id, payload)
            if name == "reset_registration":
                ResetRegistration.model_validate(arguments)
                self.store.discard(call_id)
                log_event("registration_reset", call_id=call_id)
                return {"status": "reset", "message": "Start over and collect all required fields."}
            raise AppError(400, "unknown_tool", "This registration tool is not supported.")

    def update(self, call_id: str, fields: dict[str, Any]) -> dict:
        unknown = set(fields) - PatientUpdate.model_fields.keys()
        if unknown:
            raise AppError(422, "unknown_fields", "Use only the defined demographic fields.")
        draft = self.store.get(call_id)
        draft.confirmation_token = None
        draft.prepared = None
        for name, value in fields.items():
            try:
                validated = PatientUpdate.model_validate({name: value})
                draft.values[name] = validated.model_dump(mode="json", exclude_unset=True)[name]
                draft.errors.pop(name, None)
            except ValidationError as exc:
                # Never silently keep an old value when the caller's correction is invalid.
                draft.values.pop(name, None)
                draft.errors[name] = validation_details(exc)[0]["message"]
        return {
            "status": "needs_correction" if draft.errors else "collecting",
            "collected": draft.values.copy(),
            "errors": draft.errors.copy(),
            "missing_fields": [name for name in REQUIRED_FIELDS if name not in draft.values],
            "message": "Ask only for missing or invalid fields; "
            "offer optional fields before readback.",
        }

    def prepare(self, call_id: str) -> dict:
        draft = self.store.get(call_id)
        if draft.errors:
            raise AppError(422, "invalid_draft", "Correct these fields first.", draft.errors.copy())
        payload = PatientCreate.model_validate(draft.values)
        draft.prepared = payload
        draft.confirmation_token = secrets.token_urlsafe(32)
        collected = payload.model_dump(mode="json")
        readback = "; ".join(
            f"{label}: {collected[name]}"
            for name, label in READBACK_LABELS.items()
            if collected[name] is not None
        )
        log_event("registration_prepared", call_id=call_id, payload=collected)
        return {
            "status": "awaiting_confirmation",
            "collected": collected,
            "readback": readback,
            "confirmation_token": draft.confirmation_token,
            "message": "Read every detail above. Then ask if ALL details are correct and wait for "
            "a new, explicit caller confirmation. Corrections require update and a fresh prepare.",
        }

    def save(self, session: Session, call_id: str, arguments: SaveRegistration) -> dict:
        if not arguments.caller_confirmed:
            raise AppError(
                409, "confirmation_required", "Ask the caller to confirm the full readback."
            )
        digest = hashlib.sha256(arguments.confirmation_token.encode()).hexdigest()
        # The transaction owns both inserts. A failure cannot leave a patient without a receipt.
        with session.begin():
            receipt = session.get(RegistrationReceipt, call_id)
            if receipt is not None:
                if not secrets.compare_digest(receipt.confirmation_digest, digest):
                    raise AppError(
                        409, "already_saved", "This call already completed registration."
                    )
                patient = get_patient(session, receipt.patient_id)
                return self.saved_result(patient, repeated=True)

            draft = self.store.get(call_id)
            if draft.prepared is None or draft.confirmation_token is None:
                raise AppError(
                    409, "not_prepared", "Prepare a complete readback and obtain confirmation."
                )
            if not secrets.compare_digest(
                draft.confirmation_token.encode(), arguments.confirmation_token.encode()
            ):
                raise AppError(
                    409, "stale_confirmation", "Read back the latest details and confirm again."
                )
            # Revalidate at the write boundary as well as during collection.
            payload = PatientCreate.model_validate(draft.prepared.model_dump())
            patient = add_patient(session, payload)
            session.add(
                RegistrationReceipt(
                    call_id=call_id, patient_id=patient.patient_id, confirmation_digest=digest
                )
            )
            session.flush()

        log_event(
            "registration_saved",
            call_id=call_id,
            patient_id=patient.patient_id,
            payload=payload.model_dump(mode="json"),
        )
        self.store.discard(call_id)
        return self.saved_result(patient, repeated=False)

    @staticmethod
    def saved_result(patient, repeated: bool) -> dict:
        return {
            "status": "saved",
            "repeated_request": repeated,
            "patient": PatientRead.model_validate(patient).model_dump(mode="json"),
            "message": f"You're all set, {patient.first_name}. Your registration has been saved.",
        }

    def end_call(self, call_id: str) -> None:
        draft = self.store.discard(call_id)
        if draft is not None:
            log_event("registration_abandoned", call_id=call_id, payload=draft.values)
