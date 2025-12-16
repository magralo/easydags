from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TAWAZI_")

    TAWAZI_IS_SEQUENTIAL: bool = Field(default=False, validation_alias="TAWAZI_IS_SEQUENTIAL")

    # Logger settings
    LOGURU_LEVEL: str = Field(default="CRITICAL", validation_alias="TAWAZI_LOGGER_LEVEL")
    LOGURU_BACKTRACE: bool = Field(default=False, validation_alias="TAWAZI_LOGGER_BT")
    # Caution: to set to False if used in prod (exposes variable names)
    LOGURU_DIAGNOSE: bool = Field(default=False, validation_alias="TAWAZI_LOGGER_DIAGNOSE")


Cfg = Config()
