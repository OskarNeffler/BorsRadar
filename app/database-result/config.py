import os
from dotenv import load_dotenv

# Ladda miljövariabler från .env-fil
load_dotenv()

# Databaskonfiguration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Databasnamn
PODCAST_DB_NAME = os.getenv("PODCAST_DB_NAME", "podcast-db")
NEWS_DB_NAME = os.getenv("NEWS_DB_NAME", "news-db")
USER_DB_NAME = os.getenv("USER_DB_NAME", "user-db")

# API-nycklar och konfigurationer
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# JWT-konfiguration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "30"))

# E-postkonfiguration
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Applikationskonfiguration
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# Loggningskonfiguration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Externa tjänstekonfigurationer
EXTERNAL_API_TIMEOUT = int(os.getenv("EXTERNAL_API_TIMEOUT", "10"))

# Säkerhetsinställningar
PASSWORD_RESET_TOKEN_EXPIRATION = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRATION", "3600"))  # 1 timme

# Exportera databas-URL:er (om någon vill använda dem direkt)
PODCAST_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{PODCAST_DB_NAME}"
NEWS_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{NEWS_DB_NAME}"
USER_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{USER_DB_NAME}"