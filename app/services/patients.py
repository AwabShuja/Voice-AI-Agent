from datetime import date

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, validation_details
from app.models.patient import Patient, utc_now
from app.schemas.patient import PatientCreate, PatientUpdate


def get_patient(session: Session, patient_id: str) -> Patient:
    patient = session.get(Patient, patient_id)
    if patient is None or patient.deleted_at is not None:
        raise AppError(404, "patient_not_found", "Patient was not found.")
    return patient


def list_patients(
    session: Session,
    last_name: str | None = None,
    date_of_birth: date | None = None,
    phone_number: str | None = None,
) -> list[Patient]:
    query = select(Patient).where(Patient.deleted_at.is_(None))
    if date_of_birth is not None:
        query = query.where(Patient.date_of_birth == date_of_birth)
    if phone_number is not None:
        query = query.where(Patient.phone_number == phone_number)
    patients = list(session.scalars(query.order_by(Patient.created_at.desc(), Patient.patient_id)))
    if last_name is not None:
        # SQLite lower() is ASCII-only; this also handles Unicode names in the small demo dataset.
        patients = [
            patient for patient in patients if patient.last_name.casefold() == last_name.casefold()
        ]
    return patients


def add_patient(session: Session, payload: PatientCreate) -> Patient:
    """Stage the insert; the caller owns the transaction, including any voice receipt."""
    patient = Patient(**payload.model_dump(mode="python"))
    session.add(patient)
    session.flush()
    return patient


def create_patient(session: Session, payload: PatientCreate) -> Patient:
    with session.begin():
        patient = add_patient(session, payload)
    return patient


def update_patient(session: Session, patient_id: str, payload: PatientUpdate) -> Patient:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise AppError(400, "empty_update", "Provide at least one field to update.")
    with session.begin():
        patient = get_patient(session, patient_id)
        merged = {field: getattr(patient, field) for field in PatientCreate.model_fields}
        merged.update(changes)
        try:
            validated = PatientCreate.model_validate(merged)
        except ValidationError as exc:
            raise AppError(
                422, "validation_error", "Invalid update.", validation_details(exc)
            ) from exc
        for name in changes:
            setattr(patient, name, getattr(validated, name))
        patient.updated_at = utc_now()
        session.flush()
    return patient


def delete_patient(session: Session, patient_id: str) -> Patient:
    with session.begin():
        patient = get_patient(session, patient_id)
        patient.deleted_at = patient.updated_at = utc_now()
        session.flush()
    return patient
