from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    TITLE: str
    VERSION: str
    IS_PRODUCTION: bool
    FRONTEND_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    SENTRY_DSN: str

    DATABASE_URL: str
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str

    S3_URL: str
    S3_BUCKET: str
    S3_KEY: str
    S3_SECRET: str
    S3_REGION: str

    RESEND_API_KEY: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    CRYPTOCLOUD_CREATE_INVOICE: str
    CRYPTOCLOUD_API_KEY: str
    CRYPTOCLOUD_SHOP_ID: str

    VERCEL_URL: str
    VERCEL_API_KEY: str
    VERCEL_PROJECT_ID: str

settings = Settings()