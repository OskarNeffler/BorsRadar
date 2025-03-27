from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from models import (
    NewsCompany, PodcastCompany, NewsStockPrice, News, Podcast, 
    Episode, StockMention, User, Notification
)
from datetime import datetime, timedelta
from open_ai import get_chatbot_api
import logging
import requests
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self, dbs: Dict[str, Session]):
        """
        Initiera DataProcessor med databassessioner
        
        :param dbs: Ordbok med databassessioner {'news': news_session, 'podcast': podcast_session, 'user': user_session}
        """
        self.news_db = dbs["news"]
        self.podcast_db = dbs["podcast"]
        self.user_db = dbs.get("user")
        self.chatbot = get_chatbot_api()
    
    def process_news(self, news_data):
        """
        Bearbeta råa nyhetsdata, extrahera omnämnda företag, sentiment etc.
        
        :param news_data: Ordbok med nyhetsdata
        :return: Bearbetad nyhetsobjekt
        """
        try:
            # Använd chatbot API för att analysera nyhetsinnehållet
            analysis = self.chatbot.analyze_text(news_data['content'])
            
            # Extrahera nämnda företag
            company_tickers = []
            if 'entities' in analysis:
                for entity in analysis['entities']:
                    if entity['type'] == 'COMPANY' and 'ticker' in entity:
                        company_tickers.append(entity['ticker'])
            
            # Skapa nyhetspost
            news = News(
                title=news_data['title'],
                source=news_data['source'],
                url=news_data['url'],
                published_at=datetime.fromisoformat(news_data['published_at']),
                content=news_data['content'],
                summary=analysis.get('summary', ''),
                sentiment=analysis.get('sentiment', {}).get('score', 0)
            )
            
            # Länka till nämnda företag
            for ticker in company_tickers:
                company = self.news_db.query(NewsCompany).filter(NewsCompany.ticker == ticker).first()
                if company:
                    news.companies.append(company)
                else:
                    logger.warning(f"Företag med ticker {ticker} hittades inte i nyhetsdatabasen")
                    # Skapa företaget om det inte finns
                    try:
                        new_company = NewsCompany(
                            name=ticker,  # Använd ticker som namn tills mer information finns
                            ticker=ticker,
                            sector="Unknown"
                        )
                        self.news_db.add(new_company)
                        self.news_db.commit()
                        news.companies.append(new_company)
                    except Exception as e:
                        logger.error(f"Kunde inte skapa nytt företag: {str(e)}")
            
            self.news_db.add(news)
            self.news_db.commit()
            return news
        except Exception as e:
            self.news_db.rollback()
            logger.error(f"Fel vid bearbetning av nyheter: {str(e)}")
            raise
    
    def process_podcast(self, podcast_data):
        """
        Bearbeta podcast-data, extrahera omnämnda företag, sentiment etc.
        
        :param podcast_data: Ordbok med podcast-data
        :return: Bearbetad podcast-objekt
        """
        try:
            # Använd chatbot API för att analysera podcasttranskription
            analysis = self.chatbot.analyze_text(podcast_data['transcript'])
            
            # Extrahera nämnda företag
            company_tickers = []
            if 'entities' in analysis:
                for entity in analysis['entities']:
                    if entity['type'] == 'COMPANY' and 'ticker' in entity:
                        company_tickers.append(entity['ticker'])
            
            # Skapa podcast-post
            podcast = Podcast(
                title=podcast_data['title'],
                show_name=podcast_data['show_name'],
                url=podcast_data['url'],
                published_at=datetime.fromisoformat(podcast_data['published_at']),
                duration=podcast_data['duration'],
                summary=analysis.get('summary', ''),
                transcript=podcast_data['transcript'],
                sentiment=analysis.get('sentiment', {}).get('score', 0),
                spotify_id=podcast_data.get('spotify_id'),
                youtube_id=podcast_data.get('youtube_id')
            )
            
            # Länka till nämnda företag
            for ticker in company_tickers:
                company = self.podcast_db.query(PodcastCompany).filter(PodcastCompany.ticker == ticker).first()
                if company:
                    podcast.companies.append(company)
                else:
                    logger.warning(f"Företag med ticker {ticker} hittades inte i podcast-databasen")
                    # Skapa företaget om det inte finns
                    try:
                        # Kolla först om företaget finns i nyhetsdatabasen
                        news_company = self.news_db.query(NewsCompany).filter(NewsCompany.ticker == ticker).first()
                        
                        if news_company:
                            # Skapa företaget i podcast-databasen baserat på information från nyhetsdatabasen
                            new_company = PodcastCompany(
                                name=news_company.name,
                                ticker=ticker,
                                sector=news_company.sector,
                                description=news_company.description,
                                founded_year=news_company.founded_year
                            )
                        else:
                            # Skapa företaget med minimal information
                            new_company = PodcastCompany(
                                name=ticker,  # Använd ticker som namn tills mer information finns
                                ticker=ticker,
                                sector="Unknown"
                            )
                        
                        self.podcast_db.add(new_company)
                        self.podcast_db.commit()
                        podcast.companies.append(new_company)
                    except Exception as e:
                        logger.error(f"Kunde inte skapa nytt företag: {str(e)}")
            
            self.podcast_db.add(podcast)
            self.podcast_db.commit()
            return podcast
        except Exception as e:
            self.podcast_db.rollback()
            logger.error(f"Fel vid bearbetning av podcast: {str(e)}")
            raise
    
    def get_company_data(self, ticker: str, days: int = 30) -> Dict[str, Any]:
        """
        Hämta omfattande data om ett företag inklusive aktiekurser, nyheter och podcasts
        
        :param ticker: Företagets ticker-symbol
        :param days: Antal dagar bakåt att hämta data för
        :return: Ordbok med företagsdata
        """
        # Hämta företagsinformation från båda databaserna
        news_company = self.news_db.query(NewsCompany).filter(NewsCompany.ticker == ticker).first()
        podcast_company = self.podcast_db.query(PodcastCompany).filter(PodcastCompany.ticker == ticker).first()
        
        if not news_company and not podcast_company:
            return None
        
        # Använd företagsinformation från nyhetsdatabasen om tillgänglig, annars från podcast-databasen
        company_info = {}
        if news_company:
            company_info = {
                "id": news_company.id,
                "name": news_company.name,
                "ticker": news_company.ticker,
                "sector": news_company.sector,
                "description": news_company.description,
                "founded_year": news_company.founded_year,
                "news_db_id": news_company.id,
                "podcast_db_id": None
            }
        
        if podcast_company:
            if not company_info:
                company_info = {
                    "id": podcast_company.id,
                    "name": podcast_company.name,
                    "ticker": podcast_company.ticker,
                    "sector": podcast_company.sector,
                    "description": podcast_company.description,
                    "founded_year": podcast_company.founded_year,
                    "news_db_id": None,
                    "podcast_db_id": podcast_company.id
                }
            else:
                company_info["podcast_db_id"] = podcast_company.id
        
        # Hämta aktuella aktiekurser (om företaget finns i nyhetsdatabasen)
        start_date = datetime.utcnow() - timedelta(days=days)
        stock_prices = []
        
        if news_company:
            stock_prices = (
                self.news_db.query(NewsStockPrice)
                .filter(NewsStockPrice.company_id == news_company.id)
                .filter(NewsStockPrice.date >= start_date)
                .order_by(NewsStockPrice.date)
                .all()
            )
        
        # Hämta senaste nyheter (om företaget finns i nyhetsdatabasen)
        news_items = []
        if news_company:
            news_items = (
                self.news_db.query(News)
                .join(News.companies)
                .filter(NewsCompany.id == news_company.id)
                .filter(News.published_at >= start_date)
                .order_by(desc(News.published_at))
                .all()
            )
        
        # Hämta senaste podcasts (om företaget finns i podcast-databasen)
        podcasts = []
        if podcast_company:
            podcasts = (
                self.podcast_db.query(Podcast)
                .join(Podcast.companies)
                .filter(PodcastCompany.id == podcast_company.id)
                .filter(Podcast.published_at >= start_date)
                .order_by(desc(Podcast.published_at))
                .all()
            )
        
        return {
            "company": company_info,
            "stock_prices": [
                {
                    "date": stock.date.isoformat(),
                    "open": stock.open_price,
                    "high": stock.high_price,
                    "low": stock.low_price,
                    "close": stock.close_price,
                    "volume": stock.volume
                }
                for stock in stock_prices
            ],
            "news": [
                {
                    "id": news_item.id,
                    "title": news_item.title,
                    "source": news_item.source,
                    "url": news_item.url,
                    "published_at": news_item.published_at.isoformat(),
                    "summary": news_item.summary,
                    "sentiment": news_item.sentiment
                }
                for news_item in news_items
            ],
            "podcasts": [
                {
                    "id": podcast.id,
                    "title": podcast.title,
                    "show_name": podcast.show_name,
                    "url": podcast.url,
                    "published_at": podcast.published_at.isoformat(),
                    "duration": podcast.duration,
                    "summary": podcast.summary,
                    "sentiment": podcast.sentiment,
                    "spotify_id": podcast.spotify_id,
                    "youtube_id": podcast.youtube_id
                }
                for podcast in podcasts
            ]
        }
    
    def get_trending_topics(self, days: int = 30) -> Dict[str, Any]:
        """
        Identifiera trendande ämnen, mest omnämnda företag och sentiment
        
        :param days: Antal dagar bakåt att analysera
        :return: Ordbok med trendande ämnen
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Aggregera företagsomtal från nyheter
        news_company_mentions = (
            self.news_db.query(NewsCompany.name, NewsCompany.ticker, func.count(News.id).label('mention_count'))
            .join(News.companies)
            .filter(News.published_at >= start_date)
            .group_by(NewsCompany.name, NewsCompany.ticker)
            .order_by(desc('mention_count'))
            .limit(10)
            .all()
        )
        
        # Aggregera företagsomtal från podcasts
        podcast_company_mentions = (
            self.podcast_db.query(
                StockMention.name, 
                StockMention.ticker, 
                func.count(Episode.id).label('mention_count')
            )
            .join(Episode.stock_mentions)
            .filter(Episode.published_at >= start_date)
            .group_by(StockMention.name, StockMention.ticker)
            .order_by(desc('mention_count'))
            .limit(10)
            .all()
        )
        
        # Analysera övergripande sentimenttrender
        news_sentiment = (
            self.news_db.query(
                func.avg(News.sentiment).label('avg_sentiment'),
                func.count(News.id).label('total_news')
            )
            .filter(News.published_at >= start_date)
            .first()
        )
        
        return {
            "trending_companies": {
                "from_news": [
                    {
                        "name": company.name,
                        "ticker": company.ticker,
                        "mention_count": company.mention_count
                    }
                    for company in news_company_mentions
                ],
                "from_podcasts": [
                    {
                        "name": company.name,
                        "ticker": company.ticker,
                        "mention_count": company.mention_count
                    }
                    for company in podcast_company_mentions
                ]
            },
            "sentiment_trends": {
                "news": {
                    "average_sentiment": news_sentiment.avg_sentiment,
                    "total_news": news_sentiment.total_news
                }
            }
        }
    
    def sync_companies(self):
        """
        Synkronisera företagsinformation mellan databaserna
        """
        try:
            # Hämta alla företag från nyhetsdatabasen
            news_companies = self.news_db.query(NewsCompany).all()
            
            # Hämta alla företag från podcast-databasen
            podcast_companies = self.podcast_db.query(PodcastCompany).all()
            
            # Skapa uppslagstabeller baserade på ticker
            news_company_dict = {company.ticker: company for company in news_companies}
            podcast_company_dict = {company.ticker: company for company in podcast_companies}
            
            # Synkronisera företag från nyhets- till podcast-databasen
            for ticker, news_company in news_company_dict.items():
                if ticker not in podcast_company_dict:
                    # Skapa företaget i podcast-databasen
                    new_podcast_company = PodcastCompany(
                        name=news_company.name,
                        ticker=news_company.ticker,
                        sector=news_company.sector,
                        description=news_company.description,
                        founded_year=news_company.founded_year
                    )
                    self.podcast_db.add(new_podcast_company)
            
            # Synkronisera företag från podcast- till nyhets-databasen
            for ticker, podcast_company in podcast_company_dict.items():
                if ticker not in news_company_dict:
                    # Skapa företaget i nyhetsdatabasen
                    new_news_company = NewsCompany(
                        name=podcast_company.name,
                        ticker=podcast_company.ticker,
                        sector=podcast_company.sector,
                        description=podcast_company.description,
                        founded_year=podcast_company.founded_year
                    )
                    self.news_db.add(new_news_company)
            
            # Commit ändringar
            self.podcast_db.commit()
            self.news_db.commit()
            
            return {
                "success": True,
                "message": f"Synkroniserade {len(news_company_dict)} företag från nyhets-databasen och {len(podcast_company_dict)} från podcast-databasen"
            }
        except Exception as e:
            self.podcast_db.rollback()
            self.news_db.rollback()
            logger.error(f"Fel vid synkronisering av företag: {str(e)}")
            return {
                "success": False,
                "message": f"Fel vid synkronisering: {str(e)}"
            }
    
    def create_notification_for_users(self, company_ticker: str, content: str, content_type: str, content_id: int):
        """
        Skapa notifikationer för användare som bevakar ett specifikt företag
        
        :param company_ticker: Företagets ticker-symbol
        :param content: Notifikationsinnehåll
        :param content_type: Typ av innehåll (news, podcast)
        :param content_id: ID för det relaterade innehållet
        """
        try:
            # Hitta företaget
            company = self.news_db.query(NewsCompany).filter(NewsCompany.ticker == company_ticker).first()
            
            if not company:
                logger.warning(f"Kunde inte hitta företag med ticker {company_ticker}")
                return
            
            # Hitta användare som bevakar detta företag
            watching_users = company.watching_users
            
            # Skapa notifikationer för varje användare
            for user in watching_users:
                notification = Notification(
                    user_id=user.id,
                    company_id=company.id,
                    content=content,
                    type=content_type,
                    related_content_id=content_id
                )
                self.user_db.add(notification)
            
            # Commit notifikationer
            self.user_db.commit()
            
            logger.info(f"Skapade notifikationer för {len(watching_users)} användare om {company_ticker}")
        
        except Exception as e:
            self.user_db.rollback()
            logger.error(f"Fel vid skapande av notifikationer: {str(e)}")
    
    def analyze_content(self, text: str) -> Dict[str, Any]:
        """
        Analysera innehåll med hjälp av chatboten
        
        :param text: Text att analysera
        :return: Analysresultat
        """
        try:
            # Använd chatbot för att analysera texten
            analysis = self.chatbot.analyze_text(text)
            
            return {
                "summary": analysis.get('summary', ''),
                "sentiment": analysis.get('sentiment', {}).get('score', 0),
                "entities": analysis.get('entities', []),
                "key_topics": analysis.get('key_topics', []),
                "categories": analysis.get('categories', [])
            }
        except Exception as e:
            logger.error(f"Fel vid textanalys: {str(e)}")
            return {
                "summary": "",
                "sentiment": 0,
                "entities": [],
                "key_topics": [],
                "categories": []
            }

def fetch_company_insights(ticker: str, dbs: Dict[str, Session]) -> Dict[str, Any]:
    """
    Hämta omfattande insikter för ett specifikt företag
    
    :param ticker: Företagets ticker-symbol
    :param dbs: Ordbok med databassessioner
    :return: Ordbok med företagsinsikter
    """
    processor = DataProcessor(dbs)
    
    # Hämta grundläggande företagsdata
    company_data = processor.get_company_data(ticker)
    
    if not company_data:
        return None
    
    # Hämta trendande ämnen
    trending_topics = processor.get_trending_topics()
    
    # Analysera nyheter och podcasts för ytterligare insikter
    detailed_insights = {
        "news_sentiment": sum(news.get('sentiment', 0) for news in company_data.get('news', [])) / len(company_data.get('news', [1])) if company_data.get('news') else 0,
        "podcast_sentiment": sum(podcast.get('sentiment', 0) for podcast in company_data.get('podcasts', [])) / len(company_data.get('podcasts', [1])) if company_data.get('podcasts') else 0,
        "total_mentions": {
            "news": len(company_data.get('news', [])),
            "podcasts": len(company_data.get('podcasts', []))
        }
    }
    
    return {
        "company": company_data['company'],
        "stock_prices": company_data['stock_prices'],
        "news": company_data['news'],
        "podcasts": company_data['podcasts'],
        "detailed_insights": detailed_insights,
        "trending_topics": trending_topics
    }