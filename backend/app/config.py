from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://labuser:labpassword@db:5432/network_labs"
    secret_key: str = "change-me-in-production"
    debug: bool = True
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
