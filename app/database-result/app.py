import logging
import os
import uvicorn
from dotenv import load_dotenv
from api import app as fastapi_app
from database import init_db

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Huvudfunktionen för att starta applikationen
    """
    # Ladda miljövariabler
    load_dotenv()
    
    # Logga startinformation
    logger.info("Startar Börsradar API-server")
    
    # Kontrollera att nödvändiga miljövariabler finns
    required_vars = [
        "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", 
        "PODCAST_DB_NAME", "NEWS_DB_NAME", "USER_DB_NAME",
        "OPENAI_API_KEY"
    ]
    
    # Hitta saknade variabler
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Saknade miljövariabler: {', '.join(missing_vars)}")
        logger.error("Applikationen avslutas på grund av saknade konfigurationsuppgifter")
        return
    
    # Initialisera databasen
    try:
        logger.info("Initialiserar databasanslutningar")
        init_db()
        logger.info("Databasanslutningar initialiserade")
    except Exception as e:
        logger.error(f"Kunde inte initiera databasen: {str(e)}")
        logger.error("Applikationen avslutas på grund av databasfel")
        return
    
    # Konfigurera serverinställningar
    server_config = {
        "app": fastapi_app,
        "host": os.getenv("APP_HOST", "0.0.0.0"),
        "port": int(os.getenv("APP_PORT", 8000)),
        "log_level": os.getenv("LOG_LEVEL", "info").lower(),
        "reload": os.getenv("DEBUG", "false").lower() == "true"
    }
    
    # Logga serverinformation
    logger.info(f"API-server startar på {server_config['host']}:{server_config['port']}")
    logger.info(f"Debug-läge: {'Aktiverat' if server_config['reload'] else 'Inaktiverat'}")
    
    # Starta API-servern
    try:
        uvicorn.run(**server_config)
    except Exception as e:
        logger.error(f"Fel vid start av API-server: {str(e)}")

# Kör huvudfunktionen om skriptet körs direkt
if __name__ == "__main__":
    main()

# Möjliggör import av app för WSGI-servrar
app = fastapi_app