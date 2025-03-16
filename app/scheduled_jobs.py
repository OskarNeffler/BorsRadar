import os
import glob
import logging
import time
from datetime import datetime

from app.scraper.di_scraper import DagensIndustriScraper
from app.database import SessionLocal, init_db

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("borsradar.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BorsRadar-Jobs")

def cleanup_temp_files():
    """Rensa temporära HTML-filer som skapats av skrapern."""
    logger.info("Rensar temporära filer...")
    
    # Hitta alla temporära HTML-filer
    temp_files = glob.glob("di_article_*.html") + glob.glob("di_debug.html") + glob.glob("di_page.html")
    
    if not temp_files:
        logger.info("Inga temporära filer att rensa.")
        return
    
    count = 0
    for file_path in temp_files:
        try:
            os.remove(file_path)
            count += 1
        except Exception as e:
            logger.error(f"Kunde inte ta bort fil {file_path}: {e}")
    
    logger.info(f"Rensade {count} temporära filer.")

def scrape_articles():
    """Skrapa artiklar och spara till databasen."""
    logger.info("Startar skrapning av artiklar...")
    
    scraper = DagensIndustriScraper(debug=False)  # Sätt debug=False för att undvika att skapa temporära filer
    db = SessionLocal()
    
    try:
        articles = scraper.get_news_articles(limit=30, fetch_content=True, db=db)
        logger.info(f"Skrapade och behandlade {len(articles)} artiklar")
    except Exception as e:
        logger.error(f"Fel vid skrapning: {e}")
    finally:
        db.close()

def run_all_jobs():
    """Kör alla schemalagda jobb i sekvens."""
    logger.info("Startar schemalagda jobb...")
    
    # Initiera databasen om det behövs
    try:
        init_db()
        logger.info("Databas initierad")
    except Exception as e:
        logger.error(f"Fel vid initiering av databas: {e}")
        return
    
    # Utför jobben
    try:
        # Rensa först eventuella temporära filer från tidigare körningar
        cleanup_temp_files()
        
        # Skrapa sedan nya artiklar
        scrape_articles()
        
        # Rensa efter skrapning för att städa upp eventuella nya temporära filer
        cleanup_temp_files()
    except Exception as e:
        logger.error(f"Fel vid körning av jobb: {e}")
    
    logger.info("Schemalagda jobb slutförda")

if __name__ == "__main__":
    # Kör en gång direkt när skriptet exekveras
    run_all_jobs()