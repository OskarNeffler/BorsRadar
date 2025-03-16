from app.database import init_db, engine
from app.models import Base, Article
from sqlalchemy import inspect

def check_tables():
    """Kontrollera om tabellerna finns."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Befintliga tabeller: {tables}")
    
    # Kontrollera om artikeltabellen finns
    if 'articles' in tables:
        print("✅ Artikeltabellen finns!")
        # Kontrollera kolumnerna
        columns = inspector.get_columns('articles')
        print(f"Antal kolumner i artikeltabellen: {len(columns)}")
        for column in columns:
            print(f"  - {column['name']}: {column['type']}")
    else:
        print("❌ Artikeltabellen saknas!")
    
    # Kontrollera om stock_mentions-tabellen finns
    if 'stock_mentions' in tables:
        print("✅ Stock Mentions-tabellen finns!")
    else:
        print("❌ Stock Mentions-tabellen saknas!")
    
    # Kontrollera om podcast_episodes-tabellen finns
    if 'podcast_episodes' in tables:
        print("✅ Podcast Episodes-tabellen finns!")
    else:
        print("❌ Podcast Episodes-tabellen saknas!")
    
    # Kontrollera om stock_info-tabellen finns
    if 'stock_info' in tables:
        print("✅ Stock Info-tabellen finns!")
    else:
        print("❌ Stock Info-tabellen saknas!")

if __name__ == "__main__":
    print("----- Initierar databas -----")
    try:
        init_db()
        print("✅ Databas initierad framgångsrikt!")
    except Exception as e:
        print(f"❌ Fel vid initiering av databas: {e}")
    
    print("\n----- Kontrollerar tabeller -----")
    check_tables()
    
    print("\nHantering av databas slutförd. Om du ser några fel ovan, kontrollera databasanslutningen och modellerna.")