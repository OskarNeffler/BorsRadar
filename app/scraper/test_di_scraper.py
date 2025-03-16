# Testfil för den uppdaterade DI-skrapern med databasintegration
import sys
import os
# Lägg till projektets rotmapp i Python-sökvägen för att hantera importer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.scraper.di_scraper import DagensIndustriScraper
import json
import os

# Försök importera databasrelaterade moduler, men fortsätt även om det misslyckas
try:
    from app.database import SessionLocal, init_db
    from app.models import Article
    database_available = True
except ImportError:
    print("Varning: Kunde inte importera databasmoduler. Kommer att köra utan databasintegration.")
    database_available = False

def test_scraper():
    """Test the news scraper."""
    print("Testar DI-skrapern...")
    
    # Skapa skraper med debug=True för att spara HTML
    scraper = DagensIndustriScraper(debug=True)
    
    # Försök hämta artiklar utan att använda databas först
    print("Hämtar artiklar (utan databas)...")
    articles = scraper.get_news_articles(limit=5, fetch_content=True)
    
    # Kontrollera om artiklar hittades
    if not articles:
        print("❌ Kunde inte hämta några artiklar.")
        return False
    
    print(f"✅ Hittade {len(articles)} artiklar.")
    
    # Visa första artikeln
    if articles:
        print("\nFörsta artikeln:")
        print(f"Titel: {articles[0]['title']}")
        print(f"Länk: {articles[0]['link']}")
        if articles[0].get('summary'):
            print(f"Sammanfattning: {articles[0]['summary']}")
        print(f"Tidsstämpel: {articles[0].get('timestamp', 'Ej tillgänglig')}")
        if articles[0].get('image_url'):
            print(f"Bild: {articles[0]['image_url']}")
    
    # Testa att spara artiklarna till JSON
    try:
        test_file = "test_articles.json"
        print(f"Sparar artiklar till {test_file}...")
        scraper.save_articles(articles, test_file)
        
        if os.path.exists(test_file):
            print(f"✅ Lyckades spara artiklar till {test_file}")
            # Lämna filen för inspektion
            print(f"Lämnade {test_file} för inspektion")
        else:
            print(f"❌ Kunde inte spara artiklar till {test_file}")
            return False
    except Exception as e:
        print(f"❌ Fel vid sparande av artiklar: {e}")
        return False
    
    # Testa att hämta artikelinnehåll för första artikeln
    if articles:
        try:
            print(f"Hämtar innehåll för artikeln: {articles[0]['title']}...")
            content = articles[0].get('content')
            
            if content:
                print("✅ Lyckades hämta artikelinnehåll.")
                print(f"Första 200 tecken: {content[:200]}...")
            else:
                print("⚠️ Inget innehåll hittades i artikeln.")
        except Exception as e:
            print(f"❌ Fel vid hämtning av artikelinnehåll: {e}")
    
    # Om databasintegration är tillgänglig, testa den
    if database_available:
        print("\n----- Testar databasintegration -----")
        
        # Initiera databasen
        print("Initierar databas...")
        try:
            init_db()
            print("✅ Databasen initierades framgångsrikt.")
        except Exception as e:
            print(f"❌ Fel vid initiering av databas: {e}")
            return False
        
        # Skapa en databassession
        db = SessionLocal()
        
        try:
            # Kontrollera antal artiklar i databasen före
            articles_before = db.query(Article).count()
            print(f"Artiklar i databasen före skrapning: {articles_before}")
            
            # Testa att hämta artiklar och spara till databasen
            print("\nHämtar artiklar och sparar till databas...")
            articles_with_db = scraper.get_news_articles(limit=5, fetch_content=True, db=db)
            
            if not articles_with_db:
                print("❌ Kunde inte hämta artiklar med databasintegration.")
                return False
            
            print(f"✅ Hämtade {len(articles_with_db)} artiklar med databasintegration.")
            
            # Kontrollera antal artiklar i databasen efter
            articles_after = db.query(Article).count()
            print(f"Artiklar i databasen efter skrapning: {articles_after}")
            
            new_articles = articles_after - articles_before
            if new_articles > 0:
                print(f"✅ Sparade {new_articles} nya artiklar till databasen.")
            else:
                print("⚠️ Inga nya artiklar sparades till databasen.")
                print("   (Detta är okej om alla artiklar redan fanns i databasen)")
            
            # Visa några artiklar från databasen
            db_articles = db.query(Article).order_by(Article.created_at.desc()).limit(1).all()
            
            if db_articles:
                print("\nSenaste artikel i databasen:")
                article = db_articles[0]
                print(f"ID: {article.id}")
                print(f"Artikel-ID: {article.article_id}")
                print(f"Titel: {article.title}")
                print(f"Länk: {article.link}")
                if article.summary:
                    print(f"Sammanfattning: {article.summary[:100]}...")
                if article.timestamp:
                    print(f"Tidsstämpel: {article.timestamp}")
                print(f"Källa: {article.source}")
                print(f"Skapad: {article.created_at}")
                
                print("✅ Databastestning slutförd framgångsrikt.")
            else:
                print("❌ Kunde inte hämta artiklar från databasen.")
                return False
                
        except Exception as e:
            print(f"❌ Fel under databasintegrationstestning: {e}")
            return False
        finally:
            db.close()
    else:
        print("\n⚠️ Databasintegration testades inte eftersom databasmoduler inte kunde importeras.")
    
    return True

if __name__ == "__main__":
    result = test_scraper()
    
    if result:
        print("\n✅ Alla tester passerade! Skrapern fungerar.")
    else:
        print("\n❌ Några tester misslyckades. Se felmeddelanden ovan.")