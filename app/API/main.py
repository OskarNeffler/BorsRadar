from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
import time
import logging
import json
import os
import sys
from datetime import datetime
import threading
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app/API/börsradar_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("börsradar-api")

# Ladda miljövariabler
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Importera lokala moduler med felhantering
try:
    from .podcastscraper import PodcastScraper
    from .cache_updater import NewsUpdater
    logger.info("Lokala moduler importerade framgångsrikt")
except ImportError as e:
    logger.error(f"Kunde inte importera lokala moduler: {e}")
    PodcastScraper = None
    NewsUpdater = None

# Skapa FastAPI-instans
app = FastAPI(
    title="BörsRadar API",
    description="API för aktienyheter och podcast-analys",
    version="1.0.0"
)

# Konfigurera CORS
origins = [
    "http://localhost:5173",  # Vite standardport
    "http://localhost:3000",  # React standardport
    "https://börsradar.se",   # Produktionsdomän (uppdatera med din domän)
    "*"  # Utvecklingsläge - begränsa i produktion
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Spotify och OpenAI-autentiseringsuppgifter
spotify_username = os.getenv("SPOTIFY_USERNAME", "")
spotify_password = os.getenv("SPOTIFY_PASSWORD", "")
openai_api_key = os.getenv("OPENAI_API_KEY", "")

# Initiera podcast-scraper
podcast_scraper = None
if PodcastScraper and spotify_username and spotify_password:
    try:
        podcast_scraper = PodcastScraper(
            spotify_username, 
            spotify_password, 
            openai_api_key
        )
        logger.info("PodcastScraper initierad framgångsrikt")
    except Exception as e:
        logger.error(f"Kunde inte initiera PodcastScraper: {e}")

# Modeller för datavalidering
class NewsArticle(BaseModel):
    title: str
    summary: str
    url: str
    image_url: Optional[str] = None
    date: Optional[str] = None

class PodcastRequest(BaseModel):
    podcast_namn: List[str]
    max_avsnitt: Optional[int] = 3

class StockMention(BaseModel):
    name: str
    context: str
    sentiment: str
    price_info: Optional[str] = None

# Funktioner för nyhetsinhämtning
def scrape_di_nyheter():
    """Hämta nyhetsartiklar från DI.se med Selenium"""
    try:
        # Selenium-konfiguration
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        url = "https://www.di.se/bors/nyheter/"
        driver.get(url)
        time.sleep(5)  # Vänta på att sidan ska ladda
        
        # Extrahera artiklar
        artiklar = []
        artikel_element = driver.find_elements(By.CSS_SELECTOR, "article.di-teaser")
        
        for artikel in artikel_element[:20]:  # Begränsa till 20 artiklar
            try:
                # Extrahera titel
                titel_element = artikel.find_element(By.CSS_SELECTOR, "h2.di-teaser__heading")
                titel = titel_element.text.strip()
                
                # Extrahera URL
                url_element = artikel.find_element(By.CSS_SELECTOR, "a.di-teaser__link")
                url = url_element.get_attribute("href")
                
                # Extrahera bild-URL
                bild_url = None
                try:
                    bild_element = artikel.find_element(By.CSS_SELECTOR, "img.di-teaser__image")
                    bild_url = bild_element.get_attribute("src")
                except:
                    pass
                
                # Extrahera sammanfattning
                sammanfattning = "Ingen sammanfattning"
                try:
                    sammanfattning_element = artikel.find_element(By.CSS_SELECTOR, "p.di-teaser__preamble")
                    sammanfattning = sammanfattning_element.text.strip()
                except:
                    pass
                
                # Extrahera datum
                datum = None
                try:
                    datum_element = artikel.find_element(By.CSS_SELECTOR, "time")
                    datum = datum_element.text.strip()
                except:
                    pass
                
                artiklar.append(NewsArticle(
                    title=titel,
                    summary=sammanfattning,
                    url=url,
                    image_url=bild_url,
                    date=datum
                ))
                
            except Exception as e:
                logger.error(f"Fel vid extrahering av artikeldata: {e}")
        
        driver.quit()
        return artiklar
        
    except Exception as e:
        logger.error(f"Fel vid nyhetsinhämtning: {e}")
        return []

# Globala variabler för nyhets-cache
nyhets_cache = {"data": [], "tidsstämpel": 0}
CACHE_VARAKTIGHET = 600  # 10 minuter

# API-rutter
@app.get("/")
def root():
    """Välkomstsida med information om tillgängliga endpoints"""
    return {
        "meddelande": "Välkommen till BörsRadar API",
        "endpoints": {
            "/nyheter": "Hämta senaste aktienyheterna",
            "/podcasts": "Hämta analyserade podcasts",
            "/aktier": "Hämta aktieomnämnanden från podcasts"
        }
    }

@app.get("/nyheter", response_model=List[NewsArticle])
def hämta_nyheter():
    """Hämta de senaste nyheterna"""
    nuvarande_tid = time.time()
    
    # Kontrollera om cachen behöver uppdateras
    if (nuvarande_tid - nyhets_cache["tidsstämpel"]) > CACHE_VARAKTIGHET or not nyhets_cache["data"]:
        nyheter = scrape_di_nyheter()
        nyhets_cache["data"] = nyheter
        nyhets_cache["tidsstämpel"] = nuvarande_tid
    
    return nyhets_cache["data"]

@app.get("/hälsa")
async def hälsokontroll():
    """Enkel hälsokontroll för API:et"""
    return {
        "status": "frisk",
        "podcast_scraper": "initierad" if podcast_scraper else "ej konfigurerad",
        "tidsstämpel": datetime.now().isoformat()
    }

@app.get("/podcasts")
async def hämta_analyserade_podcasts():
    """Hämta alla analyserade podcasts"""
    if not podcast_scraper:
        raise HTTPException(status_code=500, detail="Podcast-scraper är inte konfigurerad")
    
    resultat = podcast_scraper.get_latest_results()
    return {"podcasts": resultat}

@app.post("/analysera-podcasts")
async def analysera_podcasts(förfrågan: PodcastRequest):
    """Starta en ny podcast-analys"""
    if not podcast_scraper:
        raise HTTPException(status_code=500, detail="Podcast-scraper är inte konfigurerad")
    
    def kör_analys():
        try:
            podcast_scraper.run(förfrågan.podcast_namn, förfrågan.max_avsnitt)
        except Exception as e:
            logger.error(f"Fel under podcast-analys: {e}")
    
    # Kör analysen i en separat tråd
    thread = threading.Thread(target=kör_analys)
    thread.daemon = True
    thread.start()
    
    return {
        "meddelande": f"Analys startad för {len(förfrågan.podcast_namn)} podcasts", 
        "podcasts": förfrågan.podcast_namn
    }

# Global undantagshanterare
@app.exception_handler(Exception)
async def global_undantagshanterare(request: Request, exc: Exception):
    """Catch-all undantagshanterare för oväntade fel"""
    logger.error(f"Ohanterat undantag: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detalj": "Ett oväntat fel inträffade",
            "fel": str(exc)
        }
    )

# Huvudsaklig startpunkt för applikationen
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)