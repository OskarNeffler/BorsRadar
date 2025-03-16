import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
from sqlalchemy.orm import Session

# Kolla om models är tillgänglig innan import
try:
    from app.models import Article, StockMention
except ImportError:
    print("Varning: Kunde inte importera modeller - databasintegration kommer inte att fungera")
    Article = None
    StockMention = None

class DagensIndustriScraper:
    def __init__(self, debug=False):
        self.base_url = "https://www.di.se/bors/nyheter/"  # Uppdaterad URL
        self.debug = debug
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def get_news_articles(self, limit=20, fetch_content=True, db: Session = None):
        """Hämta nyhetsartiklar från Dagens Industri."""
        articles = []
        
        try:
            print("Försöker hämta artiklar från Dagens Industri...")
            response = requests.get(self.base_url, headers=self.headers)
            print(f"Status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Fel HTTP-statuskod: {response.status_code}")
                return articles
            
            # Spara HTML för debug om det behövs
            if self.debug:
                with open("di_page.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                print("Sparade HTML för debugging till di_page.html")
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Baserat på debuggningen, använd .news-item som selektor
            article_elements = soup.select('.news-item')
            print(f"Hittade {len(article_elements)} artikelelement")
            
            count = 0
            for article_elem in article_elements:
                if count >= limit:
                    break
                
                # Extrahera artikeldata med de nya selektorerna
                title_elem = article_elem.select_one('h3, h2')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                
                link_elem = article_elem.select_one('a')
                if not link_elem or 'href' not in link_elem.attrs:
                    continue
                
                link = link_elem['href']
                if not link.startswith('http'):
                    link = "https://www.di.se" + link
                
                # Extrahera artikel-ID
                article_id = re.search(r'/([^/]+)/$', link)
                if article_id:
                    article_id = article_id.group(1)
                else:
                    article_id = f"di_{count}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Extrahera bild-URL om tillgänglig
                image_url = None
                image_elem = article_elem.select_one('img')
                if image_elem and 'src' in image_elem.attrs:
                    image_url = image_elem['src']
                    if not image_url.startswith('http'):
                        image_url = "https://www.di.se" + image_url
                
                # Extrahera datum/tid
                timestamp = None
                time_elem = article_elem.select_one('.news-item__timestamp, .timestamp')
                if time_elem:
                    timestamp = time_elem.get_text(strip=True)
                
                # Extrahera sammanfattning
                summary = None
                summary_elem = article_elem.select_one('.news-item__preamble, .preamble')
                if summary_elem:
                    summary = summary_elem.get_text(strip=True)
                
                # Skapa artikelobjekt
                article_obj = {
                    'id': article_id,
                    'title': title,
                    'link': link,
                    'image_url': image_url,
                    'timestamp': timestamp,
                    'summary': summary,
                    'source': 'Dagens Industri'
                }
                
                # Hämta artikelinnehåll om så önskas
                if fetch_content:
                    try:
                        content, content_summary, exact_time = self.get_article_content(link)
                        article_obj['content'] = content
                        # Använd skrapad sammanfattning om den inte redan finns
                        if not summary and content_summary:
                            article_obj['summary'] = content_summary
                        article_obj['exact_publish_time'] = exact_time
                    except Exception as e:
                        print(f"Kunde inte hämta innehåll för artikel {article_id}: {e}")
                
                articles.append(article_obj)
                count += 1
            
            # Efter att ha skrapat artiklarna, spara till databasen om tillgänglig och om vi har models tillgängliga
            if db and Article is not None:
                print(f"Försöker spara {len(articles)} artiklar till databasen...")
                saved_count = 0
                skipped_count = 0
                
                for article_obj in articles:
                    # Kontrollera om artikeln redan finns i databasen
                    # Kolla både article_id och länk för maximal säkerhet
                    existing_article = db.query(Article).filter(
                        (Article.article_id == article_obj['id']) | 
                        (Article.link == article_obj['link'])
                    ).first()
                    
                    if not existing_article:
                        # Skapa ny artikel
                        try:
                            db_article = Article(
                                article_id=article_obj['id'],
                                title=article_obj['title'],
                                link=article_obj['link'],
                                summary=article_obj.get('summary'),
                                content=article_obj.get('content'),
                                timestamp=article_obj.get('timestamp'),
                                exact_publish_time=article_obj.get('exact_publish_time'),
                                image_url=article_obj.get('image_url'),
                                source=article_obj.get('source', 'Dagens Industri')
                            )
                            db.add(db_article)
                            db.commit()
                            db.refresh(db_article)
                            saved_count += 1
                        except Exception as e:
                            print(f"Fel vid sparande av artikel: {e}")
                            db.rollback()
                    else:
                        skipped_count += 1
                
                print(f"Sparade {saved_count} nya artiklar till databasen")
                print(f"Hoppade över {skipped_count} befintliga artiklar")
                
        except Exception as e:
            print(f"Fel vid skrapning: {e}")
        
        return articles
    
    def get_article_content(self, url):
        """Hämta innehåll från en specifik artikelsida."""
        content = ""
        summary = ""
        exact_time = ""
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Hämta ingress/sammanfattning (prova olika selektorer)
            summary_elem = soup.select_one('.article__preamble, .preamble, .di-preamble')
            if summary_elem:
                summary = summary_elem.get_text(strip=True)
            
            # Hämta exakt publiceringstid
            time_elem = soup.select_one('.article__timestamp, .timestamp, .di-timestamp')
            if time_elem:
                exact_time = time_elem.get_text(strip=True)
            
            # Hämta artikelinnehåll (prova olika selektorer för artikeltext)
            content_elements = soup.select('.article__body p, .article-body p, .di-article-body p')
            if not content_elements:
                # Prova alternativa selektorer om de ovanstående inte fungerar
                content_elements = soup.select('.article-content p, .content p')
            
            content = "\n\n".join([p.get_text(strip=True) for p in content_elements])
            
            # Om i debug-läge, spara artikelsidan för inspektion
            if self.debug:
                with open(f"di_article_{datetime.now().strftime('%Y%m%d%H%M%S')}.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                
        except Exception as e:
            print(f"Fel vid hämtning av artikelinnehåll: {e}")
        
        return content, summary, exact_time
    
    def save_articles(self, articles, filename):
        """Spara artiklar till en JSON-fil."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Fel vid sparande av artiklar till fil: {e}")
            return False

if __name__ == "__main__":
    # Snabbtest
    scraper = DagensIndustriScraper(debug=True)
    articles = scraper.get_news_articles(limit=5)
    
    print(f"Hämtade {len(articles)} artiklar:")
    for i, article in enumerate(articles):
        print(f"\n{i+1}. {article['title']}")
        print(f"   Länk: {article['link']}")
        if 'summary' in article and article['summary']:
            print(f"   Sammanfattning: {article['summary'][:100]}...")