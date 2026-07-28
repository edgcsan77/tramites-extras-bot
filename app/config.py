from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    APP_ENV: str = 'production'
    APP_HOST: str = '127.0.0.1'
    APP_PORT: int = 8110
    PUBLIC_BASE_URL: str = ''
    WEBHOOK_SECRET: str
    DATABASE_URL: str
    REDIS_URL: str
    EVOLUTION_BASE_URL: str
    EVOLUTION_API_KEY: str

    CFE_ENABLED: bool = True
    CFE_CLIENT_INSTANCES: str = 'cfeclientes'
    CFE_PROVIDER_INSTANCE: str = 'cfeproveedor'
    CFE_PROVIDER_GROUP_JID: str
    CFE_SERVICE_NUMBER_MIN_LEN: int = 8
    CFE_SERVICE_NUMBER_MAX_LEN: int = 20
    CFE_PENDING_TTL_SECONDS: int = 1800
    CFE_NO_RECORD_PHRASES: str = 'NO HAY RECIBO|NO ENCONTRADO|SIN RECIBO|NO EXISTE|NO HAY REGISTRO'

    RENAPO_ENABLED: bool = False
    RENAPO_MODE: str = 'disabled'
    RENAPO_REQUEST_TIMEOUT_SECONDS: int = 120

    @property
    def cfe_client_instances(self) -> set[str]:
        return {x.strip() for x in self.CFE_CLIENT_INSTANCES.split(',') if x.strip()}

    @property
    def cfe_no_record_phrases(self) -> tuple[str, ...]:
        return tuple(x.strip().upper() for x in self.CFE_NO_RECORD_PHRASES.split('|') if x.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
