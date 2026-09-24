from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.session import get_session
from app.schemas.patient import (
    BirthDate,
    DeletionResult,
    Name,
    PatientCreate,
    PatientRead,
    PatientUpdate,
    Phone,
)
from app.schemas.response import ApiResponse
from app.services import patients

router = APIRouter(prefix="/patients", tags=["patients"], dependencies=[Depends(require_api_key)])
Database = Annotated[Session, Depends(get_session)]


@router.get("", response_model=ApiResponse[list[PatientRead]])
def list_records(
    session: Database,
    last_name: Annotated[Name | None, Query()] = None,
    date_of_birth: Annotated[BirthDate | None, Query()] = None,
    phone_number: Annotated[Phone | None, Query()] = None,
):
    return {"data": patients.list_patients(session, last_name, date_of_birth, phone_number)}


@router.get("/{patient_id}", response_model=ApiResponse[PatientRead])
def get_record(patient_id: UUID, session: Database):
    return {"data": patients.get_patient(session, str(patient_id))}


@router.post("", status_code=201, response_model=ApiResponse[PatientRead])
def create_record(payload: PatientCreate, session: Database):
    return {"data": patients.create_patient(session, payload)}


@router.put("/{patient_id}", response_model=ApiResponse[PatientRead])
def update_record(patient_id: UUID, payload: PatientUpdate, session: Database):
    return {"data": patients.update_patient(session, str(patient_id), payload)}


@router.delete("/{patient_id}", response_model=ApiResponse[DeletionResult])
def delete_record(patient_id: UUID, session: Database):
    patient = patients.delete_patient(session, str(patient_id))
    return {"data": {"patient_id": patient.patient_id, "deleted_at": patient.deleted_at}}
