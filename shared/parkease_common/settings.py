from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "parkease-service"
    service_port: int = 8400
    environment: str = "dev"

    postgres_dsn: str = "postgresql+psycopg://parkease:parkease@postgres:5432/parkease"
    redis_url: str = "redis://redis:6379/0"
    timescale_dsn: str = "postgresql+psycopg://parkease:parkease@timescaledb:5432/parkease"
    mqtt_broker_url: str = "mqtt://mosquitto:1883"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    maps_provider_url: str = "https://tile.openstreetmap.org"
    mapbox_api_url: str = "https://api.mapbox.com"

    jwt_secret: str = "parkease-dev-secret"
    encryption_key: str = "parkease-dev-encryption-key"

    spot_status_update_target_seconds: float = 5.0
    booking_target_seconds: float = 3.0
    supported_spots_target: int = 100000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
