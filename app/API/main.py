from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
import requests
from typing import List, Optional
from pydantic import BaseModel
import time
from datetime import datetime

app = FastAPI(title="DI News Scraper API")

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NewsArticle(BaseModel):
    title: str
    summary: str
    url: str
    image_url: Optional[str] = None
    date: Optional[str] = None

@app.get("/")
def read_root():
    return {"message": "Welcome to DI News Scraper API"}

@app.get("/news", response_model=List[NewsArticle])
def get_news():
    try:
        # Make request to the target website
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        }
        response = requests.get("https://www.di.se/bors/nyheter/", headers=headers)
        response.raise_for_status()  # Raise exception for 4XX/5XX status codes
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the news list section
        news_section = soup.select_one("section.news-list__wrapper")
        if not news_section:
            raise HTTPException(status_code=404, detail="News section not found")
        
        # Extract articles
        articles = []
        for article_elem in news_section.select("article.news-item"):
            # Get date if available
            date_elem = article_elem.select_one("time")
            date = date_elem.text if date_elem else None
            
            # Get article content
            content_wrapper = article_elem.select_one(".news-item__content-wrapper")
            if not content_wrapper:
                continue
                
            link_elem = content_wrapper.select_one("a")
            if not link_elem:
                continue
                
            url = f"https://www.di.se{link_elem['href']}" if link_elem['href'].startswith('/') else link_elem['href']
            
            # Get title
            title_elem = content_wrapper.select_one("h2.news-item__heading")
            title = title_elem.text.strip() if title_elem else "No title"
            
            # Get summary
            summary_elem = content_wrapper.select_one("p.news-item__text")
            summary = summary_elem.text.strip() if summary_elem else ""
            
            # Get image if available
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
        
        return articles
    
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Error fetching news: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# If you want to add caching to avoid hitting the site too frequently
news_cache = {"data": [], "timestamp": 0}
CACHE_DURATION = 3600  # 1 hour

@app.get("/cached-news", response_model=List[NewsArticle])
def get_cached_news():
    current_time = time.time()
    if current_time - news_cache["timestamp"] > CACHE_DURATION or not news_cache["data"]:
        # Cache is expired or empty, refresh it
        news = get_news()
        news_cache["data"] = news
        news_cache["timestamp"] = current_time
        return news
    else:
        # Return cached data
        return news_cache["data"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)