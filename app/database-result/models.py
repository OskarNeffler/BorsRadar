from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

# Bas för podcast-databasen
PodcastBase = declarative_base()

# Bas för news-databasen
NewsBase = declarative_base()

# Bas för användardatabasen
UserBase = declarative_base()

# Relation mellan företag och nyheter (i news-databasen)
company_news = Table(
    'company_news',
    NewsBase.metadata,
    Column('company_id', Integer, ForeignKey('companies.id')),
    Column('news_id', Integer, ForeignKey('news.id'))
)

# Relation mellan företag och podcasts (i podcast-databasen)
company_podcasts = Table(
    'company_podcasts',
    PodcastBase.metadata,
    Column('company_id', Integer, ForeignKey('companies.id')),
    Column('podcast_id', Integer, ForeignKey('podcasts.id'))
)

# Relation mellan användare och bevakade aktier/företag
user_watched_companies = Table(
    'user_watched_companies',
    UserBase.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('company_id', Integer)  # Ta bort ForeignKey-begränsningen tills vidare
)

# Company-klassen för news-databasen
class NewsCompany(NewsBase):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    ticker = Column(String(10), nullable=False, unique=True)
    sector = Column(String(50))
    description = Column(Text)
    founded_year = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    stocks = relationship("NewsStockPrice", back_populates="company")
    news = relationship("News", secondary=company_news, back_populates="companies")
    
    def __repr__(self):
        return f"<NewsCompany(name='{self.name}', ticker='{self.ticker}')>"

# Company-klassen för podcast-databasen
class PodcastCompany(PodcastBase):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    ticker = Column(String(10), nullable=False, unique=True)
    sector = Column(String(50))
    description = Column(Text)
    founded_year = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    podcasts = relationship("Podcast", secondary=company_podcasts, back_populates="companies")
    
    def __repr__(self):
        return f"<PodcastCompany(name='{self.name}', ticker='{self.ticker}')>"

# StockPrice-klassen för news-databasen
class NewsStockPrice(NewsBase):
    __tablename__ = 'stock_prices'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    date = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    
    company = relationship("NewsCompany", back_populates="stocks")
    
    def __repr__(self):
        return f"<NewsStockPrice(company_id='{self.company_id}', date='{self.date}', close='{self.close_price}')>"

# News-klassen i news-databasen
class News(NewsBase):
    __tablename__ = 'news'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    source = Column(String(100))
    url = Column(String(500))
    published_at = Column(DateTime, nullable=False)
    content = Column(Text)
    summary = Column(Text)
    sentiment = Column(Float)  # -1 to 1 scale
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    companies = relationship("NewsCompany", secondary=company_news, back_populates="news")
    
    def __repr__(self):
        return f"<News(title='{self.title}', published_at='{self.published_at}')>"

# Podcast-klassen i podcast-databasen
class Podcast(PodcastBase):
    __tablename__ = 'podcasts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255))  # Istället för title
    playlist_id = Column(String(255))  # Ny kolumn
    
    companies = relationship("PodcastCompany", secondary=company_podcasts, back_populates="podcasts")
    episodes = relationship("Episode", back_populates="podcast")

    def __repr__(self):
        return f"<Podcast(title='{self.title}')>"

# Podcast Episode-klassen
class Episode(PodcastBase):
    __tablename__ = 'episodes'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(String(255))
    title = Column(String(255))
    video_url = Column(String(512))
    published_at = Column(DateTime)
    description = Column(Text)
    summary = Column(Text)
    transcript_length = Column(Integer)
    analysis_date = Column(DateTime)
    podcast_id = Column(Integer, ForeignKey('podcasts.id'))
    
    podcast = relationship("Podcast", back_populates="episodes")
    stock_mentions = relationship("StockMention", back_populates="episode")
    
    def __repr__(self):
        return f"<Episode(title='{self.title}')>"

# StockMention-klassen i podcast-databasen
class StockMention(PodcastBase):
    __tablename__ = 'stock_mentions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    ticker = Column(String(50))
    context = Column(Text)
    sentiment = Column(String(50))
    recommendation = Column(String(50))
    price_info = Column(String(255))
    mention_reason = Column(String(255))
    episode_id = Column(Integer, ForeignKey('episodes.id'))
    
    episode = relationship("Episode", back_populates="stock_mentions")
    
    def __repr__(self):
        return f"<StockMention(ticker='{self.ticker}', sentiment='{self.sentiment}')>"

# Användare
class User(UserBase):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relation till bevakade företag
    watched_companies = relationship(
        "NewsCompany", 
        secondary=user_watched_companies, 
        backref="watching_users"
    )
    
    # Relation till notifikationer
    notifications = relationship("Notification", back_populates="user")

# Notifikationer
class Notification(UserBase):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    company_id = Column(Integer, nullable=False)  # Ta bort ForeignKey tills databasen är skapad
    content = Column(String(500), nullable=False)
    type = Column(String(50))  # 'news', 'stock_mention', 'podcast'
    related_content_id = Column(Integer)  # ID för relaterad nyhet/podcast
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationer
    user = relationship("User", back_populates="notifications")
    company = relationship("NewsCompany", foreign_keys=[company_id])

# Tillägg från tidigare kod
class NewsArticle(NewsBase):
    __tablename__ = 'news_articles'
    
    id = Column(Integer, primary_key=True)
    title = Column(Text)
    url = Column(Text)
    summary = Column(Text)
    image_url = Column(Text)
    published_at = Column(DateTime)
    source = Column(Text)
    content = Column(Text)
    full_article_scraped = Column(Boolean)
    scraped_at = Column(DateTime)

# Chatsession för podcast-databasen
class ChatSession(PodcastBase):
    __tablename__ = 'chat_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100))
    session_id = Column(String(100), unique=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    messages = relationship("ChatMessage", back_populates="session")

# Chatmeddelanden för podcast-databasen
class ChatMessage(PodcastBase):
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('chat_sessions.id'))
    content = Column(Text, nullable=False)
    is_user = Column(Boolean, default=True)  # True if from user, False if from bot
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    session = relationship("ChatSession", back_populates="messages")