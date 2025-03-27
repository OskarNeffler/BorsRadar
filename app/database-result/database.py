from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from config import (
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, 
    PODCAST_DB_NAME, NEWS_DB_NAME
)
from models import PodcastBase, NewsBase, UserBase
from contextlib import contextmanager

# Konstruera databas-URLs
PODCAST_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{PODCAST_DB_NAME}"
NEWS_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{NEWS_DB_NAME}"
USER_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/user-db"

# Skapa två olika motorer för varje databas
podcast_engine = create_engine(PODCAST_DB_URL)
news_engine = create_engine(NEWS_DB_URL)
user_engine = create_engine(USER_DB_URL)

# Skapa sessionfabriker för varje databas
PodcastSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=podcast_engine)
NewsSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=news_engine)
UserSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=user_engine)

def init_db():
    """
    Initialisera databaser och skapa tabeller utan foreign key-kontroll
    """
    try:
        # För PostgreSQL, inaktivera foreign key-kontroller vid tabellskapande
        with podcast_engine.connect() as connection:
            connection.execute(text("SET session_replication_role = 'replica'"))
            PodcastBase.metadata.create_all(bind=connection)
            connection.execute(text("SET session_replication_role = 'origin'"))
        
        with news_engine.connect() as connection:
            connection.execute(text("SET session_replication_role = 'replica'"))
            NewsBase.metadata.create_all(bind=connection)
            connection.execute(text("SET session_replication_role = 'origin'"))
        
        with user_engine.connect() as connection:
            connection.execute(text("SET session_replication_role = 'replica'"))
            UserBase.metadata.create_all(bind=connection)
            connection.execute(text("SET session_replication_role = 'origin'"))
            
        print("Databaser initialiserade framgångsrikt")
        
    except Exception as e:
        print(f"Fel vid initialisering av databaser: {str(e)}")
        raise

@contextmanager
def get_podcast_db() -> Session:
    """
    Kontexthanterare för podcast-databasen
    """
    db = PodcastSessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_news_db() -> Session:
    """
    Kontexthanterare för news-databasen
    """
    db = NewsSessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_user_db() -> Session:
    """
    Kontexthanterare för användardatabasen
    """
    db = UserSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Funktion för att få båda databaserna för API-endpoints som behöver data från båda
def get_dbs():
    """
    Hämta sessioner för alla databaser
    """
    podcast_db = PodcastSessionLocal()
    news_db = NewsSessionLocal()
    user_db = UserSessionLocal()
    try:
        yield {
            "podcast": podcast_db, 
            "news": news_db,
            "user": user_db
        }
    finally:
        podcast_db.close()
        news_db.close()
        user_db.close()