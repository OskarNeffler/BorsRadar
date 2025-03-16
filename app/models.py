from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Article(Base):
    __tablename__ = 'articles'
    
    id = Column(Integer, primary_key=True)
    article_id = Column(String(50), unique=True)
    title = Column(String(255), nullable=False)
    link = Column(String(255), unique=True)
    summary = Column(Text)
    content = Column(Text)
    timestamp = Column(String(50))
    exact_publish_time = Column(String(50))
    image_url = Column(String(255))
    source = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation till stock mentions
    stock_mentions = relationship("StockMention", back_populates="article")

class PodcastEpisode(Base):
    __tablename__ = 'podcast_episodes'
    
    id = Column(Integer, primary_key=True)
    episode_id = Column(String(50), unique=True)
    title = Column(String(255))
    show_name = Column(String(100))
    publish_date = Column(String(50))
    transcript_path = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relation till stock mentions
    stock_mentions = relationship("StockMention", back_populates="podcast")

class StockMention(Base):
    __tablename__ = 'stock_mentions'
    
    id = Column(Integer, primary_key=True)
    stock_name = Column(String(100), nullable=False)
    article_id = Column(Integer, ForeignKey('articles.id'))
    podcast_id = Column(Integer, ForeignKey('podcast_episodes.id'))
    sentiment_score = Column(Float)
    sentiment_label = Column(String(20))
    context = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationer
    article = relationship("Article", back_populates="stock_mentions")
    podcast = relationship("PodcastEpisode", back_populates="stock_mentions")

class StockInfo(Base):
    __tablename__ = 'stock_info'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), unique=True)
    name = Column(String(100))
    sector = Column(String(100))
    market = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)