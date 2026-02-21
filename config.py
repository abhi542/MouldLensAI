from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    groq_api_key: str = ""
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "mouldlens_db"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
