from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app import models
from app.database import get_db, init_db
from app.scraper.di_scraper import DagensIndustriScraper

# Pydantic-modeller för API-svar
class ArticleBase(BaseModel):
    id: int
    article_id: str
    title: str
    link: str
    summary: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None
    image_url: Optional[str] = None
    source: str
    created_at: datetime
    
    class Config:
        orm_mode = True

# Skapa FastAPI-app
app = FastAPI(title="BörsRadar API")

# Lägg till CORS-stöd
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # För produktion, specificera din domän
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Skapa en instans av skrapern
scraper = DagensIndustriScraper()

# Endpoints
@app.get("/")
def read_root():
    return {"message": "Välkommen till BörsRadar API"}

@app.get("/api/articles", response_model=List[ArticleBase])
def get_articles(
    skip: int = 0, 
    limit: int = 20, 
    db: Session = Depends(get_db)
):
    """Hämta artiklar från databasen."""
    articles = db.query(models.Article).order_by(
        models.Article.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return articles

@app.get("/api/articles/{article_id}", response_model=ArticleBase)
def get_article(article_id: str, db: Session = Depends(get_db)):
    """Hämta specifik artikel från databasen."""
    article = db.query(models.Article).filter(
        models.Article.article_id == article_id
    ).first()
    
    if not article:
        raise HTTPException(status_code=404, detail="Artikel hittades inte")
    
    return article

@app.get("/api/refresh-articles")
def refresh_articles(limit: int = 20, db: Session = Depends(get_db)):
    """Tvinga en uppdatering av artiklar."""
    articles = scraper.get_news_articles(limit=limit, fetch_content=True, db=db)
    return {"status": "success", "message": f"Hämtade {len(articles)} artiklar"}

@app.on_event("startup")
async def startup_event():
    """Kör vid uppstart av API-servern."""
    # Initiera databas
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)