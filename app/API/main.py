from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
import time
import logging
import json
import os
import sys
from datetime import datetime
import threading
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import DictCursor


# Importera lokala moduler med felhantering
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from BorsRadar.app.API.podcast.original_podcastscraper import PodcastScraper
    from cashe_updater import NewsUpdater
    logging.getLogger("borsradar-api").info("Lokala moduler importerade framgångsrikt")
except ImportError as e:
    logging.getLogger("borsradar-api").error(f"Kunde inte importera lokala moduler: {e}")
    PodcastScraper = None
    NewsUpdater = None

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "borsradar_api.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("borsradar-api")

# Ladda miljövariabler
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Databaskonfiguration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "borsradar")
DB_USER = os.getenv("DB_USER", "borsradar")
DB_PASSWORD = os.getenv("DB_PASSWORD", "securepassword")

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

# Databasanslutningsfunktion
def get_db_connection():
    """Skapa en anslutning till PostgreSQL-databasen"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        logger.error(f"Kunde inte ansluta till databasen: {e}")
        return None

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
def get_news_from_database(limit: int = 50):
    """Hämta nyhetsartiklar från databasen"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                "SELECT title, summary, url, image_url, published_date FROM news_articles "
                "ORDER BY published_date DESC LIMIT %s",
                (limit,)
            )
            rows = cur.fetchall()
            
            articles = []
            for row in rows:
                articles.append(NewsArticle(
                    title=row['title'],
                    summary=row['summary'],
                    url=row['url'],
                    image_url=row['image_url'],
                    date=row['published_date'].isoformat() if row['published_date'] else None
                ))
            
            return articles
    except Exception as e:
        logger.error(f"Fel vid hämtning av nyheter från databas: {e}")
        return []
    finally:
        conn.close()

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
            "/aktier": "Hämta aktieomnämnanden från podcasts",
            "/halsa": "Kontrollera API:ets hälsostatus"
        }
    }

@app.get("/nyheter", response_model=List[NewsArticle])
def hämta_nyheter(limit: int = Query(50, description="Antal nyheter att hämta")):
    """Hämta de senaste nyheterna från databasen"""
    nuvarande_tid = time.time()
    
    # Kontrollera om cachen behöver uppdateras
    if (nuvarande_tid - nyhets_cache["tidsstämpel"]) > CACHE_VARAKTIGHET or not nyhets_cache["data"]:
        nyheter = get_news_from_database(limit)
        nyhets_cache["data"] = nyheter
        nyhets_cache["tidsstämpel"] = nuvarande_tid
    
    return nyhets_cache["data"]

@app.get("/halsa")
async def hälsokontroll():
    """Enkel hälsokontroll för API:et"""
    # Testa databasanslutning
    db_status = "tillgänglig"
    conn = get_db_connection()
    if not conn:
        db_status = "otillgänglig"
    else:
        conn.close()
    
    return {
        "status": "frisk",
        "podcast_scraper": "initierad" if podcast_scraper else "ej konfigurerad",
        "databas": db_status,
        "tidsstämpel": datetime.now().isoformat()
    }

@app.get("/podcasts")
async def hämta_analyserade_podcasts():
    """Hämta alla analyserade podcasts"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Databasanslutning misslyckades")
    
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # Hämta alla podcasts med antalet avsnitt
            cur.execute("""
                SELECT p.id, p.name, p.last_analyzed, COUNT(pe.id) as episode_count
                FROM podcasts p
                LEFT JOIN podcast_episodes pe ON p.id = pe.podcast_id
                GROUP BY p.id
                ORDER BY p.last_analyzed DESC
            """)
            podcasts = cur.fetchall()
            
            result = []
            for podcast in podcasts:
                podcast_data = {
                    "podcast_name": podcast['name'],
                    "analysis_date": podcast['last_analyzed'].isoformat(),
                    "episodes": []
                }
                
                # Hämta avsnitt för denna podcast
                cur.execute("""
                    SELECT pe.id, pe.title, pe.date, pe.link, pe.description, pe.has_transcript
                    FROM podcast_episodes pe
                    WHERE pe.podcast_id = %s
                    ORDER BY pe.date DESC
                """, (podcast['id'],))
                episodes = cur.fetchall()
                
                for episode in episodes:
                    episode_data = {
                        "title": episode['title'],
                        "date": episode['date'],
                        "link": episode['link'],
                        "description": episode['description'],
                        "has_transcript": episode['has_transcript'],
                        "stock_analysis": {
                            "mentions": []
                        }
                    }
                    
                    # Hämta aktieomtal för detta avsnitt
                    cur.execute("""
                        SELECT stock_name, context, sentiment, price_info
                        FROM stock_mentions
                        WHERE episode_id = %s
                    """, (episode['id'],))
                    mentions = cur.fetchall()
                    
                    for mention in mentions:
                        episode_data["stock_analysis"]["mentions"].append({
                            "name": mention['stock_name'],
                            "context": mention['context'],
                            "sentiment": mention['sentiment'],
                            "price_info": mention['price_info']
                        })
                    
                    # Lägg bara till avsnitt med aktieomtal
                    if episode_data["stock_analysis"]["mentions"]:
                        podcast_data["episodes"].append(episode_data)
                
                result.append(podcast_data)
            
            return {"podcasts": result}
            
    except Exception as e:
        logger.error(f"Fel vid hämtning av podcasts: {e}")
        raise HTTPException(status_code=500, detail=f"Databasfel: {str(e)}")
    finally:
        conn.close()

@app.get("/aktier")
async def hämta_aktieomtal(
    namn: Optional[str] = Query(None, description="Filtrera på aktienamn"),
    sentiment: Optional[str] = Query(None, description="Filtrera på sentiment (positivt, negativt, neutralt)"),
    limit: int = Query(50, description="Antal resultat att visa")
):
    """Hämta aktieomtal från podcasts med möjlighet att filtrera"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Databasanslutning misslyckades")
    
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # Skapa basquery
            query = """
                SELECT p.name AS podcast_name, pe.title, pe.date, pe.link, 
                       sm.stock_name, sm.context, sm.sentiment, sm.price_info
                FROM stock_mentions sm
                JOIN podcast_episodes pe ON sm.episode_id = pe.id
                JOIN podcasts p ON pe.podcast_id = p.id
                WHERE 1=1
            """
            
            params = []
            
            # Lägg till filter baserat på användarinput
            if namn:
                query += " AND sm.stock_name ILIKE %s"
                params.append(f"%{namn}%")
            
            if sentiment:
                query += " AND sm.sentiment ILIKE %s"
                params.append(f"%{sentiment}%")
            
            # Sortering och begränsning
            query += " ORDER BY pe.date DESC LIMIT %s"
            params.append(limit)
            
            cur.execute(query, params)
            db_mentions = cur.fetchall()
            
            # Formatera resultaten
            mentions = []
            current_episode = None
            
            for row in db_mentions:
                episode_key = f"{row['podcast_name']}:{row['title']}"
                
                # Om nytt avsnitt, skapa ny post
                if current_episode is None or current_episode['episode'] != row['title'] or current_episode['podcast'] != row['podcast_name']:
                    if current_episode is not None:
                        mentions.append(current_episode)
                    
                    current_episode = {
                        'podcast': row['podcast_name'],
                        'episode': row['title'],
                        'date': row['date'],
                        'link': row['link'],
                        'mentions': []
                    }
                
                # Lägg till aktieomtal
                current_episode['mentions'].append({
                    'name': row['stock_name'],
                    'context': row['context'],
                    'sentiment': row['sentiment'],
                    'price_info': row['price_info']
                })
            
            # Lägg till det sista episodobjektet
            if current_episode is not None:
                mentions.append(current_episode)
            
            return {"mentions": mentions}
            
    except Exception as e:
        logger.error(f"Fel vid hämtning av aktieomtal: {e}")
        raise HTTPException(status_code=500, detail=f"Databasfel: {str(e)}")
    finally:
        conn.close()

@app.post("/analysera-podcasts")
async def analysera_podcasts(förfrågan: PodcastRequest, background_tasks: BackgroundTasks):
    """Starta en ny podcast-analys i bakgrunden"""
    if not all([spotify_username, spotify_password, openai_api_key]):
        raise HTTPException(
            status_code=500, 
            detail="API saknar nödvändiga inloggningsuppgifter för Spotify eller OpenAI"
        )
    
    # Definiera bakgrundsuppgiften
    def kör_podcast_analys():
        from podcast.batch_podcast_scraper import run_podcast_analysis
        try:
            for podcast_name in förfrågan.podcast_namn:
                run_podcast_analysis(podcast_name, förfrågan.max_avsnitt)
        except Exception as e:
            logger.error(f"Fel under podcast-analys: {e}")
    
    # Schemalägg analysen i bakgrunden
    background_tasks.add_task(kör_podcast_analys)
    
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