from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid
import logging
import jwt
import secrets

# Importera egna moduler
from database import get_dbs, get_podcast_db, get_news_db, get_user_db, init_db
from models import (
    NewsCompany, PodcastCompany, News, Podcast, NewsStockPrice, 
    ChatSession, ChatMessage, NewsArticle, Episode, StockMention,
    User, Notification
)
from data_processor import DataProcessor, fetch_company_insights
from open_ai import get_chatbot_api
from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES

# Konfigurera loggning
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Skapa FastAPI-app
app = FastAPI(
    title="Börsradar API",
    description="API för finansiell data, nyheter och podcast-insights",
    version="1.0.0"
)

# Lägg till CORS-middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # I produktion, ange specifik frontend-domän
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 för lösenordshantering
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/")
def get_comprehensive_dashboard():
    """
    Hämtar en omfattande dashboard med senaste podcasts, aktieomnämnanden, och nyheter
    """
    try:
        with get_podcast_db() as podcast_db, get_news_db() as news_db:
            # Hämta de senaste podcast-avsnitten med relaterade aktieomnämnanden
            latest_episodes = podcast_db.query(Episode).order_by(Episode.published_at.desc()).limit(10).all()
            
            # Bygg strukturerad data om podcast-avsnitt och aktieomnämnanden
            episodes_data = []
            for episode in latest_episodes:
                # För varje avsnitt, hämta aktieomnämnanden
                stock_mentions = podcast_db.query(StockMention).filter(StockMention.episode_id == episode.id).all()
                
                episodes_data.append({
                    "id": episode.id,
                    "title": episode.title,
                    "published_at": episode.published_at.isoformat() if episode.published_at else None,
                    "podcast_name": episode.podcast.name if episode.podcast else "Okänd podcast",
                    "summary": episode.summary,
                    "stock_mentions": [
                        {
                            "name": mention.name,
                            "ticker": mention.ticker,
                            "sentiment": mention.sentiment,
                            "recommendation": mention.recommendation,
                            "context": mention.context
                        } for mention in stock_mentions
                    ]
                })
            
            # Hämta senaste nyheter om omnämnda aktier
            # Samla först alla omnämnda tickers för att söka relaterade nyheter
            mentioned_tickers = []
            for episode in episodes_data:
                for mention in episode["stock_mentions"]:
                    if mention["ticker"] and mention["ticker"] not in mentioned_tickers:
                        mentioned_tickers.append(mention["ticker"])
            
            # Hämta nyheter relaterade till de omnämnda aktierna
            related_news = []
            if mentioned_tickers:
                # För varje ticker, hitta relaterade nyheter
                for ticker in mentioned_tickers:
                    company = news_db.query(NewsCompany).filter(NewsCompany.ticker == ticker).first()
                    if company:
                        news_items = news_db.query(News).join(
                            News.companies
                        ).filter(
                            NewsCompany.id == company.id,
                            News.published_at >= (datetime.utcnow() - timedelta(days=30))
                        ).order_by(News.published_at.desc()).limit(5).all()
                        
                        for news in news_items:
                            related_news.append({
                                "ticker": ticker,
                                "id": news.id,
                                "title": news.title,
                                "source": news.source,
                                "published_at": news.published_at.isoformat() if news.published_at else None,
                                "sentiment": news.sentiment,
                                "summary": news.summary
                            })
            
            # Sammanfatta allt i en övergripande dashboard
            return {
                "latest_podcast_episodes": episodes_data,
                "related_news": related_news,
                "summary": {
                    "total_episodes": len(episodes_data),
                    "total_stock_mentions": sum(len(ep["stock_mentions"]) for ep in episodes_data),
                    "total_related_news": len(related_news),
                    "most_mentioned_stocks": sorted(
                        [
                            {
                                "ticker": ticker,
                                "count": sum(1 for ep in episodes_data for m in ep["stock_mentions"] if m["ticker"] == ticker)
                            } 
                            for ticker in mentioned_tickers
                        ],
                        key=lambda x: x["count"],
                        reverse=True
                    )[:5] if mentioned_tickers else []
                }
            }
    
    except Exception as e:
        logger.error(f"Fel vid hämtning av dashboard-data: {str(e)}")
        return {
            "status": "error",
            "message": "Kunde inte hämta komplett dashboard-data",
            "error": str(e)
        }
    
# Pydantic-modeller för request/response
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

class CompanyWatch(BaseModel):
    ticker: str

class NotificationResponse(BaseModel):
    id: int
    content: str
    type: str
    is_read: bool
    created_at: datetime

# Nya modeller för podcasts och episoder
class StockMentionResponse(BaseModel):
    id: int
    name: str
    ticker: Optional[str] = None
    context: Optional[str] = None
    sentiment: Optional[str] = None
    recommendation: Optional[str] = None
    price_info: Optional[str] = None
    mention_reason: Optional[str] = None

class EpisodeResponse(BaseModel):
    id: int
    video_id: Optional[str] = None
    title: Optional[str] = None
    video_url: Optional[str] = None
    published_at: Optional[datetime] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    transcript_length: Optional[int] = None
    analysis_date: Optional[datetime] = None
    stock_mentions: List[StockMentionResponse] = []

class PodcastResponse(BaseModel):
    id: int
    name: Optional[str] = None
    playlist_id: Optional[str] = None
    episodes: List[EpisodeResponse] = []

# Autentiseringsfunktioner
def create_access_token(data: dict):
    """
    Skapa en JWT-token
    """
    to_encode = data.copy()
    expires = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    to_encode.update({"exp": expires})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_user(token: str, user_db: Session):
    """
    Hämta aktuell användare från JWT-token
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Kunde inte validera autentiseringsuppgifter")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Kunde inte validera autentiseringsuppgifter")
    
    user = user_db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Användare hittades inte")
    return user

# Initierings-endpoint
@app.on_event("startup")
def startup_event():
    """
    Initiera databaser när applikationen startar
    """
    init_db()

# Användare och autentisering
@app.post("/users/register")
def register_user(user: UserCreate, user_db: Session = Depends(get_user_db)):
    """
    Registrera en ny användare
    """
    # Kontrollera om användarnamn eller e-post redan finns
    existing_user = user_db.query(User).filter(
        or_(User.username == user.username, User.email == user.email)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Användarnamn eller e-post är redan registrerat")
    
    # Skapa ny användare
    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=secrets.token_hex(32),  # Tillfällig hashning
        is_active=True
    )
    
    user_db.add(new_user)
    user_db.commit()
    user_db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email
    )

@app.post("/users/login")
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    user_db: Session = Depends(get_user_db)
):
    """
    Användarinloggning
    """
    user = user_db.query(User).filter(User.username == form_data.username).first()
    
    if not user or user.password_hash != secrets.token_hex(32):
        raise HTTPException(
            status_code=401,
            detail="Felaktigt användarnamn eller lösenord"
        )
    
    # Uppdatera senaste inloggning
    user.last_login = datetime.utcnow()
    user_db.commit()
    
    # Skapa åtkomsttoken
    access_token = create_access_token({"sub": user.username})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }

@app.post("/users/watch-company")
def watch_company(
    company: CompanyWatch, 
    token: str = Depends(oauth2_scheme),
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Lägg till ett företag i användarens bevakningslista
    """
    # Hämta användare
    current_user = get_current_user(token, dbs["user"])
    
    # Hitta företaget
    company_obj = dbs["news"].query(NewsCompany).filter(NewsCompany.ticker == company.ticker).first()
    
    if not company_obj:
        raise HTTPException(status_code=404, detail="Företaget hittades inte")
    
    # Kontrollera om företaget redan bevakas
    if company_obj in current_user.watched_companies:
        raise HTTPException(status_code=400, detail="Företaget bevakas redan")
    
    # Lägg till företaget i bevakningslistan
    current_user.watched_companies.append(company_obj)
    dbs["user"].commit()
    
    return {
        "message": f"Börjar bevaka {company_obj.name} ({company_obj.ticker})",
        "company": {
            "id": company_obj.id,
            "name": company_obj.name,
            "ticker": company_obj.ticker
        }
    }

@app.get("/users/notifications")
def get_user_notifications(
    token: str = Depends(oauth2_scheme),
    user_db: Session = Depends(get_user_db),
    only_unread: bool = False
):
    """
    Hämta användarens notifikationer
    """
    # Hämta användare
    current_user = get_current_user(token, user_db)
    
    # Hämta notifikationer
    query = user_db.query(Notification).filter(Notification.user_id == current_user.id)
    
    if only_unread:
        query = query.filter(Notification.is_read == False)
    
    notifications = query.order_by(Notification.created_at.desc()).all()
    
    return [
        NotificationResponse(
            id=notification.id,
            content=notification.content,
            type=notification.type,
            is_read=notification.is_read,
            created_at=notification.created_at
        )
        for notification in notifications
    ]

# Insights och analys-endpoints
@app.get("/insights/company/{ticker}")
def get_company_insights(
    ticker: str,
    days: int = 30,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Hämta omfattande insikter för ett specifikt företag
    """
    insights = fetch_company_insights(ticker, dbs)
    
    if not insights:
        raise HTTPException(status_code=404, detail="Inga insikter hittades för denna ticker")
    
    return insights

@app.get("/insights/trending")
def get_trending_insights(
    days: int = 30,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Hämta trendande ämnen och företag
    """
    processor = DataProcessor(dbs)
    
    try:
        trending_topics = processor.get_trending_topics(days)
        return trending_topics
    except Exception as e:
        logger.error(f"Fel vid hämtning av trendande ämnen: {str(e)}")
        raise HTTPException(status_code=500, detail="Kunde inte hämta trendande ämnen")

# Nya endpoints för podcasts
@app.get("/podcasts", response_model=List[PodcastResponse])
def get_all_podcasts(podcast_db: Session = Depends(get_podcast_db)):
    """
    Hämta alla podcasts med episoder och aktieomnämnanden
    """
    try:
        # Hämta alla podcasts
        podcasts = podcast_db.query(Podcast).all()
        
        # Bygg strukturerad data med alla relationer
        podcasts_data = []
        for podcast in podcasts:
            # Hämta alla episoder för denna podcast
            episodes = podcast_db.query(Episode).filter(Episode.podcast_id == podcast.id).all()
            
            episodes_data = []
            for episode in episodes:
                # Hämta aktieomnämnanden för denna episod
                stock_mentions = podcast_db.query(StockMention).filter(StockMention.episode_id == episode.id).all()
                
                episodes_data.append(
                    EpisodeResponse(
                        id=episode.id,
                        video_id=episode.video_id,
                        title=episode.title,
                        video_url=episode.video_url,
                        published_at=episode.published_at,
                        description=episode.description,
                        summary=episode.summary,
                        transcript_length=episode.transcript_length,
                        analysis_date=episode.analysis_date,
                        stock_mentions=[
                            StockMentionResponse(
                                id=mention.id,
                                name=mention.name,
                                ticker=mention.ticker,
                                context=mention.context,
                                sentiment=mention.sentiment,
                                recommendation=mention.recommendation,
                                price_info=mention.price_info,
                                mention_reason=mention.mention_reason
                            ) for mention in stock_mentions
                        ]
                    )
                )
            
            podcasts_data.append(
                PodcastResponse(
                    id=podcast.id,
                    name=podcast.name,
                    playlist_id=podcast.playlist_id,
                    episodes=episodes_data
                )
            )
        
        return podcasts_data
    
    except Exception as e:
        logger.error(f"Fel vid hämtning av podcasts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta podcasts: {str(e)}")

@app.get("/podcasts/{podcast_id}", response_model=PodcastResponse)
def get_podcast_by_id(podcast_id: int, podcast_db: Session = Depends(get_podcast_db)):
    """
    Hämta en specifik podcast med alla episoder och aktieomnämnanden
    """
    try:
        # Hämta podcast med angivet ID
        podcast = podcast_db.query(Podcast).filter(Podcast.id == podcast_id).first()
        
        if not podcast:
            raise HTTPException(status_code=404, detail="Podcast hittades inte")
        
        # Hämta alla episoder för denna podcast
        episodes = podcast_db.query(Episode).filter(Episode.podcast_id == podcast.id).all()
        
        episodes_data = []
        for episode in episodes:
            # Hämta aktieomnämnanden för denna episod
            stock_mentions = podcast_db.query(StockMention).filter(StockMention.episode_id == episode.id).all()
            
            episodes_data.append(
                EpisodeResponse(
                    id=episode.id,
                    video_id=episode.video_id,
                    title=episode.title,
                    video_url=episode.video_url,
                    published_at=episode.published_at,
                    description=episode.description,
                    summary=episode.summary,
                    transcript_length=episode.transcript_length,
                    analysis_date=episode.analysis_date,
                    stock_mentions=[
                        StockMentionResponse(
                            id=mention.id,
                            name=mention.name,
                            ticker=mention.ticker,
                            context=mention.context,
                            sentiment=mention.sentiment,
                            recommendation=mention.recommendation,
                            price_info=mention.price_info,
                            mention_reason=mention.mention_reason
                        ) for mention in stock_mentions
                    ]
                )
            )
        
        return PodcastResponse(
            id=podcast.id,
            name=podcast.name,
            playlist_id=podcast.playlist_id,
            episodes=episodes_data
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fel vid hämtning av podcast: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta podcast: {str(e)}")

@app.get("/episodes", response_model=List[EpisodeResponse])
def get_all_episodes(
    limit: int = 50, 
    offset: int = 0,
    podcast_id: Optional[int] = None,
    podcast_db: Session = Depends(get_podcast_db)
):
    """
    Hämta alla episoder med aktieomnämnanden, med möjlighet att filtrera på podcast
    """
    try:
        # Bygg query med filter om podcast_id finns
        query = podcast_db.query(Episode)
        if podcast_id is not None:
            query = query.filter(Episode.podcast_id == podcast_id)
        
        # Hämta episoder med paginering
        episodes = query.order_by(Episode.published_at.desc()).offset(offset).limit(limit).all()
        
        episodes_data = []
        for episode in episodes:
            # Hämta aktieomnämnanden för denna episod
            stock_mentions = podcast_db.query(StockMention).filter(StockMention.episode_id == episode.id).all()
            
            episodes_data.append(
                EpisodeResponse(
                    id=episode.id,
                    video_id=episode.video_id,
                    title=episode.title,
                    video_url=episode.video_url,
                    published_at=episode.published_at,
                    description=episode.description,
                    summary=episode.summary,
                    transcript_length=episode.transcript_length,
                    analysis_date=episode.analysis_date,
                    stock_mentions=[
                        StockMentionResponse(
                            id=mention.id,
                            name=mention.name,
                            ticker=mention.ticker,
                            context=mention.context,
                            sentiment=mention.sentiment,
                            recommendation=mention.recommendation,
                            price_info=mention.price_info,
                            mention_reason=mention.mention_reason
                        ) for mention in stock_mentions
                    ]
                )
            )
        
        return episodes_data
    
    except Exception as e:
        logger.error(f"Fel vid hämtning av episoder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta episoder: {str(e)}")

@app.get("/episodes/{episode_id}", response_model=EpisodeResponse)
def get_episode_by_id(episode_id: int, podcast_db: Session = Depends(get_podcast_db)):
    """
    Hämta en specifik episod med alla aktieomnämnanden
    """
    try:
        # Hämta episod med angivet ID
        episode = podcast_db.query(Episode).filter(Episode.id == episode_id).first()
        
        if not episode:
            raise HTTPException(status_code=404, detail="Episod hittades inte")
        
        # Hämta aktieomnämnanden för denna episod
        stock_mentions = podcast_db.query(StockMention).filter(StockMention.episode_id == episode.id).all()
        
        return EpisodeResponse(
            id=episode.id,
            video_id=episode.video_id,
            title=episode.title,
            video_url=episode.video_url,
            published_at=episode.published_at,
            description=episode.description,
            summary=episode.summary,
            transcript_length=episode.transcript_length,
            analysis_date=episode.analysis_date,
            stock_mentions=[
                StockMentionResponse(
                    id=mention.id,
                    name=mention.name,
                    ticker=mention.ticker,
                    context=mention.context,
                    sentiment=mention.sentiment,
                    recommendation=mention.recommendation,
                    price_info=mention.price_info,
                    mention_reason=mention.mention_reason
                ) for mention in stock_mentions
            ]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fel vid hämtning av episod: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta episod: {str(e)}")

# Lägg till dessa imports och endpoints i din api.py-fil

from typing import Optional, List
from pydantic import BaseModel

# Nya modeller för relaterat innehåll
class RelatedContentRequest(BaseModel):
    query: Optional[str] = None
    content_type: Optional[str] = "mixed"  # "news", "podcast", "mixed"
    max_days: Optional[int] = 30
    limit: Optional[int] = 100

class SearchRequest(BaseModel):
    query: str
    content_type: Optional[str] = "mixed"  # "news", "podcast", "mixed"
    max_days: Optional[int] = 30
    max_results: Optional[int] = 10

# Nya endpoints för relaterat innehåll
@app.post("/content/related")
def find_related_content(
    request: RelatedContentRequest,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Hitta och gruppera relaterat innehåll mellan nyheter och podcasts
    """
    try:
        # Hämta chatbot API för analys
        chatbot = get_chatbot_api()
        content_items = []
        
        # Sätt tidsgräns
        start_date = datetime.utcnow() - timedelta(days=request.max_days)
        
        # Hämta nyhetsinnehåll om efterfrågat
        if request.content_type in ["news", "mixed"]:
            news_items = (
                dbs["news"].query(News)
                .filter(News.published_at >= start_date)
                .order_by(News.published_at.desc())
                .limit(request.limit)
                .all()
            )
            
            content_items.extend([{
                "id": news.id,
                "type": "news",
                "title": news.title,
                "content": news.content,
                "summary": news.summary,
                "source": news.source,
                "published_at": news.published_at.isoformat() if news.published_at else None,
                "url": news.url,
                "sentiment": news.sentiment
            } for news in news_items])
        
        # Hämta podcast-innehåll om efterfrågat
        if request.content_type in ["podcast", "mixed"]:
            episodes = (
                dbs["podcast"].query(Episode)
                .filter(Episode.published_at >= start_date)
                .order_by(Episode.published_at.desc())
                .limit(request.limit)
                .all()
            )
            
            for episode in episodes:
                # Hämta podcast-namn
                podcast_name = episode.podcast.name if episode.podcast else "Okänd podcast"
                
                # Hämta aktieomnämnanden för denna episod
                stock_mentions = dbs["podcast"].query(StockMention).filter(StockMention.episode_id == episode.id).all()
                
                content_items.append({
                    "id": episode.id,
                    "type": "podcast",
                    "title": episode.title,
                    "description": episode.description,
                    "summary": episode.summary,
                    "podcast_name": podcast_name,
                    "published_at": episode.published_at.isoformat() if episode.published_at else None,
                    "video_url": episode.video_url,
                    "stock_mentions": [
                        {
                            "name": mention.name,
                            "ticker": mention.ticker,
                            "sentiment": mention.sentiment,
                            "recommendation": mention.recommendation,
                            "context": mention.context
                        } for mention in stock_mentions
                    ]
                })
        
        # Använd AI för att gruppera innehållet
        topic_groups = chatbot.find_related_content(content_items, request.content_type)
        
        return {
            "status": "success",
            "topic_groups": topic_groups,
            "content_count": len(content_items),
            "topic_count": len(topic_groups) if topic_groups else 0
        }
    
    except Exception as e:
        logger.error(f"Fel vid hämtning av relaterat innehåll: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hitta relaterat innehåll: {str(e)}")

@app.post("/content/search")
def search_content(
    request: SearchRequest,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Sök och analysera innehåll baserat på en sökfråga
    """
    try:
        # Hämta chatbot API för analys
        chatbot = get_chatbot_api()
        content_items = []
        
        # Sätt tidsgräns
        start_date = datetime.utcnow() - timedelta(days=request.max_days)
        
        # Hämta nyhetsinnehåll om efterfrågat
        if request.content_type in ["news", "mixed"]:
            news_items = (
                dbs["news"].query(News)
                .filter(News.published_at >= start_date)
                .order_by(News.published_at.desc())
                .limit(200)  # Hämta tillräckligt med data för sökning
                .all()
            )
            
            content_items.extend([{
                "id": news.id,
                "type": "news",
                "title": news.title,
                "content": news.content,
                "summary": news.summary,
                "source": news.source,
                "published_at": news.published_at.isoformat() if news.published_at else None,
                "url": news.url,
                "sentiment": news.sentiment
            } for news in news_items])
        
        # Hämta podcast-innehåll om efterfrågat
        if request.content_type in ["podcast", "mixed"]:
            episodes = (
                dbs["podcast"].query(Episode)
                .filter(Episode.published_at >= start_date)
                .order_by(Episode.published_at.desc())
                .limit(200)  # Hämta tillräckligt med data för sökning
                .all()
            )
            
            for episode in episodes:
                # Hämta podcast-namn
                podcast_name = episode.podcast.name if episode.podcast else "Okänd podcast"
                
                # Hämta aktieomnämnanden för denna episod
                stock_mentions = dbs["podcast"].query(StockMention).filter(StockMention.episode_id == episode.id).all()
                
                content_items.append({
                    "id": episode.id,
                    "type": "podcast",
                    "title": episode.title,
                    "description": episode.description,
                    "summary": episode.summary,
                    "podcast_name": podcast_name,
                    "published_at": episode.published_at.isoformat() if episode.published_at else None,
                    "video_url": episode.video_url,
                    "stock_mentions": [
                        {
                            "name": mention.name,
                            "ticker": mention.ticker,
                            "sentiment": mention.sentiment,
                            "recommendation": mention.recommendation,
                            "context": mention.context
                        } for mention in stock_mentions
                    ]
                })
        
        # Använd AI för att söka och analysera innehållet
        search_results = chatbot.search_and_analyze(request.query, content_items, request.max_results)
        
        return {
            "status": "success",
            "query": request.query,
            "results": search_results.get("results", []),
            "query_analysis": search_results.get("query_analysis", {}),
            "total_content_searched": len(content_items)
        }
    
    except Exception as e:
        logger.error(f"Fel vid sökning i innehåll: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte söka i innehåll: {str(e)}")

@app.get("/content/topics")
def get_trending_topics(
    days: int = 30,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Hämta trendande ämnen baserat på nyheter och podcast-omnämnanden
    """
    try:
        # Hämta chatbot API för analys
        chatbot = get_chatbot_api()
        content_items = []
        
        # Sätt tidsgräns
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Hämta nyhetsinnehåll
        news_items = (
            dbs["news"].query(News)
            .filter(News.published_at >= start_date)
            .order_by(News.published_at.desc())
            .limit(100)
            .all()
        )
        
        content_items.extend([{
            "id": news.id,
            "type": "news",
            "title": news.title,
            "content": news.content,
            "summary": news.summary,
            "published_at": news.published_at.isoformat() if news.published_at else None
        } for news in news_items])
        
        # Hämta podcast-innehåll
        episodes = (
            dbs["podcast"].query(Episode)
            .filter(Episode.published_at >= start_date)
            .order_by(Episode.published_at.desc())
            .limit(100)
            .all()
        )
        
        content_items.extend([{
            "id": episode.id,
            "type": "podcast",
            "title": episode.title,
            "description": episode.description,
            "summary": episode.summary,
            "published_at": episode.published_at.isoformat() if episode.published_at else None
        } for episode in episodes])
        
        # Använd AI för att identifiera trendande ämnen
        topic_groups = chatbot.find_related_content(content_items, "mixed")
        
        # Räkna antal innehållsobjekt per ämne för att identifiera trender
        trending_topics = []
        for topic_id, topic_data in topic_groups.items():
            item_count = len(topic_data.get("items", []))
            
            # Beräkna medelsentiment
            sentiment_values = []
            for item in topic_data.get("items", []):
                if "sentiment" in item:
                    # För nyheter
                    sentiment_values.append(item.get("sentiment", 0))
                elif "stock_mentions" in item:
                    # För podcasts med aktieomnämnanden, ta medelvärdet av sentiment
                    mentions = item.get("stock_mentions", [])
                    for mention in mentions:
                        if mention.get("sentiment"):
                            # Konvertera eventuella textbaserade sentiment till nummer
                            sentiment_text = mention.get("sentiment", "").lower()
                            if "positiv" in sentiment_text:
                                sentiment_values.append(0.5)
                            elif "negativ" in sentiment_text:
                                sentiment_values.append(-0.5)
                            elif "neutral" in sentiment_text:
                                sentiment_values.append(0)
            
            avg_sentiment = sum(sentiment_values) / len(sentiment_values) if sentiment_values else 0
            
            trending_topics.append({
                "topic_id": topic_id,
                "topic": topic_data.get("topic", ""),
                "summary": topic_data.get("summary", ""),
                "keywords": topic_data.get("keywords", []),
                "item_count": item_count,
                "sentiment": avg_sentiment,
                # Räkna antal av varje typ
                "news_count": sum(1 for item in topic_data.get("items", []) if item.get("type") == "news"),
                "podcast_count": sum(1 for item in topic_data.get("items", []) if item.get("type") == "podcast")
            })
        
        # Sortera ämnen efter antal omnämnanden (trendande)
        trending_topics.sort(key=lambda x: x["item_count"], reverse=True)
        
        return {
            "status": "success",
            "trending_topics": trending_topics,
            "total_content_analyzed": len(content_items),
            "time_period_days": days
        }
    
    except Exception as e:
        logger.error(f"Fel vid hämtning av trendande ämnen: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta trendande ämnen: {str(e)}")

@app.get("/content/ticker/{ticker}")
def get_content_by_ticker(
    ticker: str,
    days: int = 30,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Hämta och klassificera allt innehåll relaterat till en specifik ticker
    """
    try:
        # Hämta chatbot API för analys
        chatbot = get_chatbot_api()
        content_items = []
        
        # Sätt tidsgräns
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Hitta företaget i nyhetsdatabasen
        news_company = dbs["news"].query(NewsCompany).filter(NewsCompany.ticker == ticker).first()
        
        # Hämta nyheter om företaget finns
        if news_company:
            news_items = (
                dbs["news"].query(News)
                .join(News.companies)
                .filter(NewsCompany.id == news_company.id)
                .filter(News.published_at >= start_date)
                .order_by(News.published_at.desc())
                .all()
            )
            
            content_items.extend([{
                "id": news.id,
                "type": "news",
                "title": news.title,
                "content": news.content,
                "summary": news.summary,
                "source": news.source,
                "published_at": news.published_at.isoformat() if news.published_at else None,
                "url": news.url,
                "sentiment": news.sentiment
            } for news in news_items])
        
        # Hämta podcast-episoder som nämner denna ticker
        episodes_with_mentions = (
            dbs["podcast"].query(Episode)
            .join(StockMention, StockMention.episode_id == Episode.id)
            .filter(StockMention.ticker == ticker)
            .filter(Episode.published_at >= start_date)
            .order_by(Episode.published_at.desc())
            .all()
        )
        
        for episode in episodes_with_mentions:
            # Hämta podcast-namn
            podcast_name = episode.podcast.name if episode.podcast else "Okänd podcast"
            
            # Hämta aktieomnämnanden för denna episod och ticker
            stock_mentions = (
                dbs["podcast"].query(StockMention)
                .filter(StockMention.episode_id == episode.id)
                .filter(StockMention.ticker == ticker)
                .all()
            )
            
            content_items.append({
                "id": episode.id,
                "type": "podcast",
                "title": episode.title,
                "description": episode.description,
                "summary": episode.summary,
                "podcast_name": podcast_name,
                "published_at": episode.published_at.isoformat() if episode.published_at else None,
                "video_url": episode.video_url,
                "stock_mentions": [
                    {
                        "name": mention.name,
                        "ticker": mention.ticker,
                        "sentiment": mention.sentiment,
                        "recommendation": mention.recommendation,
                        "context": mention.context
                    } for mention in stock_mentions
                ]
            })
        
        # Gruppera innehållet efter ämnen
        topic_groups = {}
        if content_items:
            topic_groups = chatbot.find_related_content(content_items, "mixed")
        
        # Sammanställ statistik om ticker-omnämnanden
        stats = {
            "total_mentions": len(content_items),
            "news_mentions": sum(1 for item in content_items if item.get("type") == "news"),
            "podcast_mentions": sum(1 for item in content_items if item.get("type") == "podcast"),
            "sentiment_distribution": {
                "positive": 0,
                "neutral": 0,
                "negative": 0
            },
            "recommendation_distribution": {
                "buy": 0,
                "hold": 0,
                "sell": 0,
                "none": 0
            }
        }
        
        # Räkna sentiment- och rekommendationsfördelning
        for item in content_items:
            if item.get("type") == "news" and "sentiment" in item:
                sentiment = float(item.get("sentiment", 0))
                if sentiment > 0.2:
                    stats["sentiment_distribution"]["positive"] += 1
                elif sentiment < -0.2:
                    stats["sentiment_distribution"]["negative"] += 1
                else:
                    stats["sentiment_distribution"]["neutral"] += 1
            
            elif item.get("type") == "podcast" and "stock_mentions" in item:
                for mention in item.get("stock_mentions", []):
                    # Sentiment
                    sentiment_text = mention.get("sentiment", "").lower()
                    if "positiv" in sentiment_text:
                        stats["sentiment_distribution"]["positive"] += 1
                    elif "negativ" in sentiment_text:
                        stats["sentiment_distribution"]["negative"] += 1
                    else:
                        stats["sentiment_distribution"]["neutral"] += 1
                    
                    # Rekommendationer
                    recommendation = mention.get("recommendation", "").lower()
                    if "köp" in recommendation or "buy" in recommendation:
                        stats["recommendation_distribution"]["buy"] += 1
                    elif "sälj" in recommendation or "sell" in recommendation:
                        stats["recommendation_distribution"]["sell"] += 1
                    elif "håll" in recommendation or "hold" in recommendation:
                        stats["recommendation_distribution"]["hold"] += 1
                    else:
                        stats["recommendation_distribution"]["none"] += 1
        
        # Hämta företagsinfo om den finns
        company_info = None
        if news_company:
            company_info = {
                "id": news_company.id,
                "name": news_company.name,
                "ticker": news_company.ticker,
                "sector": news_company.sector,
                "description": news_company.description
            }
        
        return {
            "status": "success",
            "company": company_info,
            "content": content_items,
            "topic_groups": topic_groups,
            "stats": stats,
            "time_period_days": days
        }
    
    except Exception as e:
        logger.error(f"Fel vid hämtning av innehåll för ticker {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta innehåll för ticker {ticker}: {str(e)}")

# Lägg till dessa endpoints i din api.py-fil

@app.get("/news-articles")
def get_news_articles(
    limit: int = 50,
    offset: int = 0,
    days: int = 30,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Hämta alla nyhetsartiklar från news_articles-tabellen
    """
    try:
        # Sätt tidsgräns
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Hämta nyhetsartiklar från news-db
        news_articles = (
            dbs["news"].query(NewsArticle)
            .filter(NewsArticle.published_at >= start_date if NewsArticle.published_at is not None else True)
            .order_by(NewsArticle.published_at.desc() if NewsArticle.published_at is not None else NewsArticle.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        # Mappa till respons-modell
        articles = [
            {
                "id": article.id,
                "title": article.title,
                "url": article.url,
                "summary": article.summary,
                "image_url": article.image_url,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "source": article.source,
                "content": article.content,
                "full_article_scraped": article.full_article_scraped,
                "scraped_at": article.scraped_at.isoformat() if article.scraped_at else None
            } 
            for article in news_articles
        ]
        
        # Total antal artiklar för paginering
        total_count = (
            dbs["news"].query(func.count(NewsArticle.id))
            .filter(NewsArticle.published_at >= start_date if NewsArticle.published_at is not None else True)
            .scalar()
        )
        
        return {
            "status": "success",
            "total": total_count,
            "offset": offset,
            "limit": limit,
            "news_articles": articles
        }
    
    except Exception as e:
        logger.error(f"Fel vid hämtning av nyhetsartiklar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta nyhetsartiklar: {str(e)}")

@app.get("/news-articles/{article_id}")
def get_news_article_by_id(
    article_id: int,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Hämta en specifik nyhetsartikel med ID
    """
    try:
        article = dbs["news"].query(NewsArticle).filter(NewsArticle.id == article_id).first()
        
        if not article:
            raise HTTPException(status_code=404, detail="Nyhetsartikel hittades inte")
        
        return {
            "status": "success",
            "article": {
                "id": article.id,
                "title": article.title,
                "url": article.url,
                "summary": article.summary,
                "image_url": article.image_url,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "source": article.source,
                "content": article.content,
                "full_article_scraped": article.full_article_scraped,
                "scraped_at": article.scraped_at.isoformat() if article.scraped_at else None
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fel vid hämtning av nyhetsartikel {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta nyhetsartikeln: {str(e)}")

@app.get("/companies-with-news")
def get_companies_with_news(
    days: int = 30,
    dbs: Dict[str, Session] = Depends(get_dbs)
):
    """
    Hämta företag och deras relaterade nyheter
    """
    try:
        # Sätt tidsgräns
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Hämta alla företag
        companies = dbs["news"].query(NewsCompany).all()
        
        result = []
        for company in companies:
            # Hämta relaterade nyheter för företaget
            news_items = (
                dbs["news"].query(News)
                .join(News.companies)
                .filter(NewsCompany.id == company.id)
                .filter(News.published_at >= start_date if News.published_at is not None else True)
                .order_by(News.published_at.desc() if News.published_at is not None else News.id.desc())
                .limit(5)
                .all()
            )
            
            if news_items:  # Bara inkludera företag med nyheter
                result.append({
                    "company": {
                        "id": company.id,
                        "name": company.name,
                        "ticker": company.ticker,
                        "sector": company.sector
                    },
                    "news_count": len(news_items),
                    "latest_news": [
                        {
                            "id": news.id,
                            "title": news.title,
                            "published_at": news.published_at.isoformat() if news.published_at else None,
                            "sentiment": news.sentiment
                        }
                        for news in news_items
                    ]
                })
        
        # Sortera efter antal nyheter
        result.sort(key=lambda x: x["news_count"], reverse=True)
        
        return {
            "status": "success",
            "companies_with_news": result
        }
    
    except Exception as e:
        logger.error(f"Fel vid hämtning av företag med nyheter: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kunde inte hämta företag med nyheter: {str(e)}")

# För att köra appen med Uvicorn direkt
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)