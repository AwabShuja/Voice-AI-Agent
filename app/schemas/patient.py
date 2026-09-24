import re
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

import phonenumbers
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
    model_validator,
)

US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT "
    "NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
REQUIRED_FIELDS = (
    "first_name",
    "last_name",
    "date_of_birth",
    "sex",
    "phone_number",
    "address_line_1",
    "city",
    "state",
    "zip_code",
)


def validate_name(value: str) -> str:
    if not any(char.isalpha() for char in value) or any(
        not (char.isalpha() or char in "-'") for char in value
    ):
        raise ValueError("Use letters, hyphens, and apostrophes only")
    return value


def parse_birth_date(value) -> date:
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", value):
        raise ValueError("Use MM/DD/YYYY with a four-digit year")
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError as exc:
        raise ValueError("Enter a valid calendar date in MM/DD/YYYY") from exc


def validate_birth_date(value: date) -> date:
    if value > datetime.now(UTC).date():
        raise ValueError("Date of birth must not be in the future")
    return value


def normalize_phone(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\+?[0-9().\s-]+", value.strip()):
        raise ValueError("Enter a U.S. phone number using digits and standard phone punctuation")
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if not re.fullmatch(r"[2-9][0-9]{2}[2-9][0-9]{6}", digits):
        raise ValueError("Enter a 10-digit U.S. phone number with a valid area and exchange code")
    if not phonenumbers.is_valid_number_for_region(phonenumbers.parse(digits, "US"), "US"):
        raise ValueError("Enter a valid U.S. phone number")
    return digits


def validate_state(value: str) -> str:
    if value not in US_STATES:
        raise ValueError("Use a two-letter U.S. state abbreviation, or DC")
    return value


class Sex(StrEnum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE = "Decline to Answer"


Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
    AfterValidator(validate_name),
]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Phone = Annotated[str, BeforeValidator(normalize_phone)]
State = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True), AfterValidator(validate_state)
]
ZipCode = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{5}(-[0-9]{4})?$")
]
MemberID = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9]+$"
    ),
]
BirthDate = Annotated[
    date,
    BeforeValidator(parse_birth_date),
    AfterValidator(validate_birth_date),
    PlainSerializer(
        lambda value: f"{value.month:02d}/{value.day:02d}/{value.year:04d}",
        return_type=str,
        when_used="json",
    ),
    WithJsonSchema(
        {"type": "string", "pattern": r"^\d{2}/\d{2}/\d{4}$", "examples": ["02/29/2000"]}
    ),
]


class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: Name
    last_name: Name
    date_of_birth: BirthDate
    sex: Sex
    phone_number: Phone
    address_line_1: Address
    city: ShortText
    state: State
    zip_code: ZipCode
    email: EmailStr | None = None
    address_line_2: Address | None = None
    insurance_provider: ShortText | None = None
    insurance_member_id: MemberID | None = None
    preferred_language: ShortText | None = "English"
    emergency_contact_name: ShortText | None = None
    emergency_contact_phone: Phone | None = None


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: Name | None = None
    last_name: Name | None = None
    date_of_birth: BirthDate | None = None
    sex: Sex | None = None
    phone_number: Phone | None = None
    address_line_1: Address | None = None
    city: ShortText | None = None
    state: State | None = None
    zip_code: ZipCode | None = None
    email: EmailStr | None = None
    address_line_2: Address | None = None
    insurance_provider: ShortText | None = None
    insurance_member_id: MemberID | None = None
    preferred_language: ShortText | None = None
    emergency_contact_name: ShortText | None = None
    emergency_contact_phone: Phone | None = None

    @model_validator(mode="after")
    def required_fields_cannot_be_cleared(self):
        for name in self.model_fields_set.intersection(REQUIRED_FIELDS):
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class PatientRead(PatientCreate):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class DeletionResult(BaseModel):
    patient_id: UUID
    deleted_at: datetime
