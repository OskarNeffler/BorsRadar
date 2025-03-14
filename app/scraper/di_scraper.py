import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import json
from datetime import datetime
import os

class DagensIndustriScraper:
    def __init__(self, debug=False):
        self.base_url = "https://www.di.se/bors/nyheter/"  # Notera att jag har uppdaterat URL:en baserat på dina framgångsrika test
        self.chrome_options = Options()
        if not debug:
            self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        # Lägg till user agent för att bättre simulera en vanlig webbläsare
        self.chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.debug = debug

    def get_news_articles(self, limit=20):
        """Scrape latest news articles from Dagens Industri."""
        print(f"Öppnar webbläsare och navigerar till {self.base_url}...")
        driver = webdriver.Chrome(options=self.chrome_options)
        driver.get(self.base_url)
        
        # Vänta på att sidan laddas
        print("Väntar på att sidan ska laddas...")
        time.sleep(5)
        
        html = driver.page_source
        
        # Om debug, spara HTML för inspektion
        if self.debug:
            with open("di_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Sparade HTML till di_debug.html för felsökning")
        
        driver.quit()
        
        print("Analyserar HTML...")
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        
        # Försök hitta artiklar med olika selektorer
        print("Letar efter artiklar med olika selektorer...")
        
        # Första försöket: Baserat på HTML-exemplet du delade
        news_section = soup.select_one('.news-list__wrapper')
        if news_section:
            article_elements = news_section.select('.news-item')
            print(f"Metod 1: Hittade {len(article_elements)} artiklar med .news-list__wrapper > .news-item")
        else:
            article_elements = []
            print("Metod 1: Hittade ingen .news-list__wrapper")
        
        # Andra försöket: Leta direkt efter nyhetsartiklar
        if not article_elements:
            article_elements = soup.select('.news-item')
            print(f"Metod 2: Hittade {len(article_elements)} artiklar med .news-item")
        
        # Tredje försöket: Leta efter alla artiklar
        if not article_elements:
            article_elements = soup.select('article')
            print(f"Metod 3: Hittade {len(article_elements)} artiklar med 'article'-taggen")
        
        if not article_elements:
            print("Kunde inte hitta några artikelelement med något av tillvägagångssätten")
            return []
            
        print(f"Hittade totalt {len(article_elements)} artiklar. Bearbetar upp till {limit} artiklar...")
        
        # Begränsa antalet artiklar enligt limit
        article_elements = article_elements[:limit]
        
        for i, article in enumerate(article_elements):
            try:
                print(f"\nBearbetar artikel {i+1}...")
                
                # Försök hitta länk
                link_elem = article.select_one('a[href]')
                if not link_elem:
                    print("Ingen länk hittad, hoppar över")
                    continue
                    
                link = link_elem['href']
                if not link.startswith('http'):
                    link = self.base_url + link
                print(f"Länk: {link}")
                
                # Försök hitta rubrik med flera olika selektorer
                heading_selectors = ['.news-item__heading', 'h2', 'h3', '.heading', '.title']
                heading_elem = None
                for selector in heading_selectors:
                    heading_elem = article.select_one(selector)
                    if heading_elem:
                        print(f"Hittade rubrik med selector '{selector}'")
                        break
                
                if not heading_elem and link_elem.text.strip():
                    print("Använder länktext som rubrik")
                    title = link_elem.text.strip()
                elif heading_elem:
                    title = heading_elem.text.strip()
                else:
                    print("Ingen rubrik hittad, hoppar över")
                    continue
                
                print(f"Rubrik: {title}")
                
                # Försök hitta text/sammanfattning med flera olika selektorer
                summary_selectors = ['.news-item__text', 'p', '.summary', '.description', '.preamble']
                summary = ""
                for selector in summary_selectors:
                    summary_elem = article.select_one(selector)
                    if summary_elem:
                        summary = summary_elem.text.strip()
                        print(f"Hittade sammanfattning med selector '{selector}'")
                        break
                
                print(f"Sammanfattning: {summary[:50]}..." if summary else "Ingen sammanfattning")
                
                # Försök hitta datum med flera olika selektorer
                time_selectors = ['time', '.date', '.time', '.timestamp']
                timestamp = datetime.now().strftime("%Y-%m-%d")
                for selector in time_selectors:
                    time_elem = article.select_one(selector)
                    if time_elem:
                        timestamp = time_elem.text.strip()
                        print(f"Hittade tidsstämpel med selector '{selector}': {timestamp}")
                        break
                
                # Kontrollera om det finns en bild
                image_selectors = ['.image__el', 'img', '.image']
                image_url = None
                for selector in image_selectors:
                    image_elem = article.select_one(selector)
                    if image_elem and 'src' in image_elem.attrs:
                        image_url = image_elem['src']
                        print(f"Hittade bild med selector '{selector}'")
                        break
                
                articles.append({
                    'title': title,
                    'link': link,
                    'summary': summary,
                    'timestamp': timestamp,
                    'image_url': image_url,
                    'source': 'Dagens Industri'
                })
                print(f"Artikel {i+1} har lagts till")
                
            except Exception as e:
                print(f"Fel vid bearbetning av artikel {i+1}: {e}")
                continue
        
        print(f"Lyckades hämta {len(articles)} artiklar.")
        return articles
        
    def save_articles(self, articles, filename="test_articles.json"):
        """Save scraped articles to JSON file."""
        # Kontrollera och skapa sökväg om den innehåller en mapp
        if '/' in filename:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        print(f"Sparar {len(articles)} artiklar till {filename}...")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=4)
            
        print(f"Artiklarna har sparats till {filename}")
            
    def get_article_content(self, url):
        """Get the full content of a specific article."""
        driver = webdriver.Chrome(options=self.chrome_options)
        driver.get(url)
        time.sleep(3)
        
        html = driver.page_source
        driver.quit()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Försök hitta artikelinnehållet med olika selektorer
        content_selectors = [
            '.article__body', 
            '.article-content',
            '.article-text',
            '.news-article__content',
            '.text-content',
            '.content',
            'article p'
        ]
        
        for selector in content_selectors:
            content_elements = soup.select(selector)
            if content_elements:
                content = '\n'.join([el.get_text().strip() for el in content_elements])
                if content:
                    return content
                
        return None

# Om skriptet körs direkt, hämta och spara artiklar
if __name__ == "__main__":
    scraper = DagensIndustriScraper(debug=True)
    articles = scraper.get_news_articles(limit=10)
    
    if articles:
        # Skriv ut de första artiklarna
        for i, article in enumerate(articles[:3]):
            print(f"\nArtikel {i+1}:")
            print(f"Titel: {article['title']}")
            print(f"Länk: {article['link']}")
            print(f"Sammanfattning: {article['summary']}")
            print(f"Tidsstämpel: {article['timestamp']}")
            if article.get('image_url'):
                print(f"Bild: {article['image_url']}")
        
        # Spara alla artiklar
        scraper.save_articles(articles)
    else:
        print("Kunde inte hitta några artiklar.")