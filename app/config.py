from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://bible:bible@localhost:5432/bible"

    embedding_model: str = "BAAI/bge-small-en-v1.5"


settings = Settings()
