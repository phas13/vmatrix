from pydantic import BaseModel, ConfigDict, Field


class SystemSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    promotion_threshold: int
    default_competency_domain: str


class SystemSettingsUpdate(BaseModel):
    promotion_threshold: int | None = Field(None, ge=1, le=100)
    default_competency_domain: str | None = Field(None, min_length=1, max_length=100)


class CredentialResetResponse(BaseModel):
    temporary_password: str
    message: str
