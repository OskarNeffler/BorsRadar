# Testfil för den uppdaterade DI-skrapern
from di_scraper import DagensIndustriScraper
import os

def test_scraper():
    """Test the news scraper."""
    print("Testar DI-skrapern...")
    
    # Kör med debug=True för att spara HTML för felsökning
    scraper = DagensIndustriScraper(debug=True)
    
    # Försök hämta artiklar
    print("Hämtar artiklar...")
    articles = scraper.get_news_articles(limit=5)
    
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
        print(f"Sammanfattning: {articles[0]['summary']}")
        print(f"Tidsstämpel: {articles[0]['timestamp']}")
        if articles[0].get('image_url'):
            print(f"Bild: {articles[0]['image_url']}")
    
    # Testa att spara artiklarna
    try:
        test_file = "test_articles.json"  # Enkel filnamn utan mappar
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
            content = scraper.get_article_content(articles[0]['link'])
            
            if content:
                print("✅ Lyckades hämta artikelinnehåll.")
                print(f"Första 200 tecken: {content[:200]}...")
            else:
                print("❌ Kunde inte hämta artikelinnehåll.")
        except Exception as e:
            print(f"❌ Fel vid hämtning av artikelinnehåll: {e}")
    
    return True

if __name__ == "__main__":
    result = test_scraper()
    
    if result:
        print("\n✅ Alla tester passerade! Skrapern fungerar.")
    else:
        print("\n❌ Några tester misslyckades. Se felmeddelanden ovan.")