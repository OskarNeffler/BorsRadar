from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
import requests
from typing import List, Optional
from pydantic import BaseModel
import time
from datetime import datetime
import os
import json
import sys
import logging
from dotenv import load_dotenv

# Ladda miljövariabler från .env-filen
load_dotenv()

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api")

# Lägg till relativ import för PodcastScraper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from podcastscraper import PodcastScraper
    logger.info("PodcastScraper importerad")
except ImportError as e:
    logger.error(f"Kunde inte importera PodcastScraper: {e}")
    PodcastScraper = None

# Skapa FastAPI-instans
app = FastAPI(title="BörsRadar API")

# Spotify-inloggningsuppgifter från miljövariabler
spotify_username = os.getenv("SPOTIFY_USERNAME", "")
spotify_password = os.getenv("SPOTIFY_PASSWORD", "")

# Skapa scraper endast om inloggningsuppgifter finns
podcast_scraper = None
if PodcastScraper and spotify_username and spotify_password:
    try:
        podcast_scraper = PodcastScraper(spotify_username, spotify_password)
        logger.info("PodcastScraper initierad")
    except Exception as e:
        logger.error(f"Fel vid initiering av PodcastScraper: {e}")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # För produktion, ange specifika domäner
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------
# Modeller
# --------------------------------------------------------------

class NewsArticle(BaseModel):
    title: str
    summary: str
    url: str
    image_url: Optional[str] = None
    date: Optional[str] = None

class PodcastRequest(BaseModel):
    podcast_names: List[str]  # Lista av podcastnamn att analysera
    max_episodes: Optional[int] = 3  # Antal avsnitt per podcast att analysera

class StockMention(BaseModel):
    name: str               # Aktie/företagsnamn
    context: str            # Kontexten där det nämndes (citat)
    sentiment: str          # Positivt, negativt eller neutralt omnämnande
    price_info: Optional[str] = None  # Eventuell prisinformation

class EpisodeMention(BaseModel):
    podcast: str           # Podcast-namn
    episode: str           # Avsnittets titel
    date: str              # Publiceringsdatum
    link: str              # Länk till avsnittet
    mentions: List[StockMention]  # Lista med aktieomtal i avsnittet

# --------------------------------------------------------------
# Hjälpfunktioner
# --------------------------------------------------------------

def fetch_news_from_source():
    """Hämtar nyheter från Dagens Industri"""
    logger.info("Hämtar nyheter från Dagens Industri")
    try:
        # Skapa en request till målwebbplatsen
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        }
        response = requests.get("https://www.di.se/bors/nyheter/", headers=headers)
        response.raise_for_status()  # Kasta undantag för 4XX/5XX statuskoder
        
        # Parsa HTML-innehållet
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Hitta nyhetssektionen
        news_section = soup.select_one("section.news-list__wrapper")
        if not news_section:
            logger.error("Kunde inte hitta nyhetssektionen")
            raise HTTPException(status_code=404, detail="News section not found")
        
        # Extrahera artiklar
        articles = []
        for article_elem in news_section.select("article.news-item"):
            # Hämta datum om tillgängligt
            date_elem = article_elem.select_one("time")
            date = date_elem.text if date_elem else None
            
            # Hämta artikelinnehåll
            content_wrapper = article_elem.select_one(".news-item__content-wrapper")
            if not content_wrapper:
                continue
                
            link_elem = content_wrapper.select_one("a")
            if not link_elem:
                continue
                
            url = f"https://www.di.se{link_elem['href']}" if link_elem['href'].startswith('/') else link_elem['href']
            
            # Hämta titel
            title_elem = content_wrapper.select_one("h2.news-item__heading")
            title = title_elem.text.strip() if title_elem else "Ingen titel"
            
            # Hämta sammanfattning
            summary_elem = content_wrapper.select_one("p.news-item__text")
            summary = summary_elem.text.strip() if summary_elem else ""
            
            # Hämta bild om tillgänglig
            image_elem = article_elem.select_one("img.image__el")
            image_url = None
            if image_elem and 'src' in image_elem.attrs:
                image_url = image_elem['src']
            
            articles.append(
                NewsArticle(
                    title=title,
                    summary=summary,
                    url=url,
                    image_url=image_url,
                    date=date
                )
            )
        
        logger.info(f"Hämtade {len(articles)} artiklar")
        return articles
    
    except requests.RequestException as e:
        logger.error(f"Nätverksfel: {e}")
        raise HTTPException(status_code=503, detail=f"Error fetching news: {str(e)}")
    except Exception as e:
        logger.error(f"Oväntat fel: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# Cache för nyheter
news_cache = {"data": [], "timestamp": 0}
CACHE_DURATION = 3600  # 1 timme - hur länge cachen är giltig

# --------------------------------------------------------------
# Rutter - Nyheter
# --------------------------------------------------------------

@app.get("/")
def read_root():
    """Välkomstsida med information om tillgängliga endpoints"""
    return {
        "message": "Välkommen till BörsRadar API",
        "endpoints": {
            "/news": "Hämta senaste nyheter från DI",
            "/podcasts": "Hämta analyserade podcasts",
            "/stocks": "Hämta aktieomtal från podcasts",
            "/analyze-podcasts": "Starta ny podcast-analys"
        }
    }

@app.get("/news", response_model=List[NewsArticle])
def get_news():
    """Hämta färska nyheter direkt från källan"""
    return fetch_news_from_source()

@app.get("/cached-news", response_model=List[NewsArticle])
def get_cached_news():
    """Hämta nyheter från cachen, eller uppdatera om cachen är för gammal"""
    current_time = time.time()
    if current_time - news_cache["timestamp"] > CACHE_DURATION or not news_cache["data"]:
        # Cachen är utgången eller tom, uppdatera den
        news = fetch_news_from_source()
        news_cache["data"] = news
        news_cache["timestamp"] = current_time
        return news
    else:
        # Returnera cacheade data
        return news_cache["data"]

# --------------------------------------------------------------
# Rutter - Podcasts
# --------------------------------------------------------------

@app.get("/podcasts")
async def get_analyzed_podcasts():
    """Hämta alla analyserade podcasts."""
    if not podcast_scraper:
        raise HTTPException(status_code=500, detail="Podcast-scraper är inte konfigurerad")
    
    # Hämta resultat från tidigare analyser
    results = podcast_scraper.get_latest_results()
    return {"podcasts": results}

@app.get("/podcasts/{podcast_name}")
async def get_podcast_analysis(podcast_name: str):
    """Hämta analys för en specifik podcast."""
    if not podcast_scraper:
        raise HTTPException(status_code=500, detail="Podcast-scraper är inte konfigurerad")
    
    # Hämta resultat för en specifik podcast
    result = podcast_scraper.get_latest_results(podcast_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Ingen analys hittad för {podcast_name}")
    return result

@app.get("/stocks")
async def get_stock_mentions(stock_name: Optional[str] = None):
    """
    Hämta omnämnanden av aktier.
    Om stock_name anges, filtrera efter det aktienamnet.
    """
    if not podcast_scraper:
        raise HTTPException(status_code=500, detail="Podcast-scraper är inte konfigurerad")
    
    # Hämta aktieomtal, med valfri filtrering på aktienamn
    mentions = podcast_scraper.get_stock_mentions(stock_name)
    return {"mentions": mentions}

@app.post("/analyze-podcasts")
async def analyze_podcasts(request: PodcastRequest):
    """
    Starta en ny analys av podcasts.
    Detta är en långkörande process som körs i bakgrunden.
    """
    if not podcast_scraper:
        raise HTTPException(status_code=500, detail="Podcast-scraper är inte konfigurerad")
    
    # Starta analysen i en separat tråd för att inte blockera API:t
    import threading
    
    def run_analysis():
        podcast_scraper.run(request.podcast_names, request.max_episodes)
    
    thread = threading.Thread(target=run_analysis)
    thread.daemon = True
    thread.start()
    
    return {"message": f"Analys startad för {len(request.podcast_names)} podcasts"}

# --------------------------------------------------------------
# Huvud-entry point
# --------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)