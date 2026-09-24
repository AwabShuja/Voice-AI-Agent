from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UpdateRegistration(ToolArguments):
    fields: dict[str, Any] = Field(min_length=1, max_length=16)


class PrepareRegistration(ToolArguments):
    pass


class SaveRegistration(ToolArguments):
    confirmation_token: str = Field(min_length=20, max_length=200)
    caller_confirmed: StrictBool


class ResetRegistration(ToolArguments):
    pass
