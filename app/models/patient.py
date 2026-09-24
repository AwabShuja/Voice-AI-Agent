from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """SQLite stores naive datetimes; the application always reads and writes UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint("length(first_name) BETWEEN 1 AND 50", name="ck_first_name_length"),
        CheckConstraint("length(last_name) BETWEEN 1 AND 50", name="ck_last_name_length"),
        CheckConstraint("length(city) BETWEEN 1 AND 100", name="ck_city_length"),
        CheckConstraint("length(trim(address_line_1)) > 0", name="ck_address_required"),
        CheckConstraint("sex IN ('Male', 'Female', 'Other', 'Decline to Answer')", name="ck_sex"),
        CheckConstraint(
            "length(phone_number) = 10 AND phone_number NOT GLOB '*[^0-9]*'",
            name="ck_phone",
        ),
        CheckConstraint("length(state) = 2", name="ck_state_length"),
        CheckConstraint("length(zip_code) IN (5, 10)", name="ck_zip_length"),
        CheckConstraint(
            "emergency_contact_phone IS NULL OR (length(emergency_contact_phone) = 10 "
            "AND emergency_contact_phone NOT GLOB '*[^0-9]*')",
            name="ck_emergency_phone",
        ),
        CheckConstraint(
            "insurance_member_id IS NULL OR (length(insurance_member_id) > 0 "
            "AND insurance_member_id NOT GLOB '*[^a-zA-Z0-9]*')",
            name="ck_member_id",
        ),
    )

    patient_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50), index=True)
    date_of_birth: Mapped[date] = mapped_column(Date, index=True)
    sex: Mapped[str] = mapped_column(String(20))
    phone_number: Mapped[str] = mapped_column(String(10), index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    address_line_1: Mapped[str] = mapped_column(String(200))
    address_line_2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(10))
    insurance_provider: Mapped[str | None] = mapped_column(String(100))
    insurance_member_id: Mapped[str | None] = mapped_column(String(100))
    preferred_language: Mapped[str | None] = mapped_column(String(100))
    emergency_contact_name: Mapped[str | None] = mapped_column(String(100))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)


class RegistrationReceipt(Base):
    """One successful registration per provider call, including across process restarts."""

    __tablename__ = "registration_receipts"

    call_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), unique=True)
    confirmation_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
