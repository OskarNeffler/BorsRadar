import schedule
import time
import logging
import os
import sys
import glob
import traceback
from datetime import datetime

# Konfigurera loggning
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BorsRadar-Scheduler")

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

def run_scraper_job():
    """Kör skraperjobbet med felhantering."""
    from app.scraper.di_scraper import DagensIndustriScraper
    from app.database import SessionLocal, init_db
    
    logger.info("Startar skrapningsjobb...")
    
    try:
        # Initiera databasen
        init_db()
        logger.info("Databas initierad")
        
        # Rensa först eventuella temporära filer
        cleanup_temp_files()
        
        # Skapa skraper och databassession
        scraper = DagensIndustriScraper(debug=False)
        db = SessionLocal()
        
        try:
            # Skrapa och spara artiklar
            articles = scraper.get_news_articles(limit=30, fetch_content=True, db=db)
            logger.info(f"Skrapningsjobb slutfört: bearbetade {len(articles)} artiklar")
        except Exception as e:
            logger.error(f"Fel vid skrapning: {e}")
            logger.error(traceback.format_exc())
        finally:
            db.close()
        
        # Rensa upp temporära filer efter skrapning
        cleanup_temp_files()
        
    except Exception as e:
        logger.error(f"Kritiskt fel i skrapningsjobbet: {e}")
        logger.error(traceback.format_exc())

def main():
    """Huvudfunktion för schemaläggaren."""
    logger.info("BörsRadar schemaläggare startar...")
    
    # Kör jobbet direkt vid start
    logger.info("Kör initial skrapning...")
    run_scraper_job()
    
    # Schemalägg jobbet att köra varje timme
    schedule.every(1).hours.do(run_scraper_job)
    logger.info("Skrapningsjobb schemalagt att köra varje timme")
    
    # Huvudloop
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Kontrollera varje minut
    except KeyboardInterrupt:
        logger.info("Schemaläggaren avbröts av användaren")
    except Exception as e:
        logger.critical(f"Oväntat fel i schemaläggaren: {e}")
        logger.critical(traceback.format_exc())
        raise

if __name__ == "__main__":
    main()