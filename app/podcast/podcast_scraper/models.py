from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Podcast(Base):
    __tablename__ = 'podcasts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    playlist_id = Column(String(255))
    episodes = relationship("Episode", back_populates="podcast")
    
    def __repr__(self):
        return f"<Podcast(name='{self.name}')>"

class Episode(Base):
    __tablename__ = 'episodes'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(String(255), unique=True, nullable=False)
    title = Column(String(255))
    video_url = Column(String(512))
    published_at = Column(DateTime)
    description = Column(Text)
    summary = Column(Text)
    transcript_length = Column(Integer)
    analysis_date = Column(DateTime)
    
    podcast_id = Column(Integer, ForeignKey('podcasts.id'))
    podcast = relationship("Podcast", back_populates="episodes")
    mentions = relationship("StockMention", back_populates="episode")
    
    def __repr__(self):
        return f"<Episode(title='{self.title}')>"

class StockMention(Base):
    __tablename__ = 'stock_mentions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    ticker = Column(String(50))
    context = Column(Text)
    sentiment = Column(String(50))
    recommendation = Column(String(50))
    price_info = Column(String(255))
    mention_reason = Column(String(255))
    
    episode_id = Column(Integer, ForeignKey('episodes.id'))
    episode = relationship("Episode", back_populates="mentions")
    
    def __repr__(self):
        return f"<StockMention(name='{self.name}', sentiment='{self.sentiment}')>"