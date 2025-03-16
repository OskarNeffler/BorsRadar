from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Ladda miljövariabler från .env-filen
load_dotenv()

# Databasanslutning
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://oskar:password@localhost/borsradar")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialisera databasen och skapa tabeller."""
    from app.models import Base
    Base.metadata.create_all(bind=engine)