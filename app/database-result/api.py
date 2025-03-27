from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional, Dict, Any
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
                            News.published_at >= (datetime.datetime.utcnow() - datetime.timedelta(days=30))
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

# Lägg till fler endpoints efter behov...

# För att köra appen med Uvicorn direkt
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)