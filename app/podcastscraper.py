from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import os
import logging
from datetime import datetime
from openai import OpenAI
import re

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('podcast_scraper.log')
    ]
)

logger = logging.getLogger('podcast_scraper')

# Initiera OpenAI klient
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class PodcastScraper:
    def __init__(self, spotify_username, spotify_password):
        self.spotify_username = spotify_username
        self.spotify_password = spotify_password
        self.driver = None
        self.results_dir = "podcast_data"
        
        # Skapa mapp för resultat om den inte finns
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
    
    def setup_driver(self):
        """Konfigurera webdriver med rätt inställningar."""
        logger.info("Konfigurerar Chrome webdriver")
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Kör i headless-läge
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logger.info("Chrome webdriver konfigurerad")
    
    def login_to_spotify(self):
        """Logga in på Spotify Web Player."""
        logger.info("Försöker logga in på Spotify")
        try:
            self.driver.get("https://open.spotify.com/")
            time.sleep(2)
            
            # Acceptera cookies om dialogrutan visas
            try:
                cookie_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Acceptera')]"))
                )
                cookie_button.click()
                logger.info("Accepterade cookies")
            except:
                logger.info("Ingen cookie-prompt hittades")
            
            # Klicka på login-knappen
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log in') or contains(text(), 'Logga in')]"))
            )
            login_button.click()
            
            # Fyll i användarnamn och lösenord
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "login-username"))
            )
            username_field = self.driver.find_element(By.ID, "login-username")
            password_field = self.driver.find_element(By.ID, "login-password")
            
            username_field.send_keys(self.spotify_username)
            password_field.send_keys(self.spotify_password)
            
            # Klicka på logga in-knappen
            login_submit = self.driver.find_element(By.ID, "login-button")
            login_submit.click()
            
            # Vänta på att inloggningen slutförs
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='user-widget-link']"))
            )
            
            logger.info("Inloggning lyckades!")
            return True
        except Exception as e:
            logger.error(f"Inloggning misslyckades: {e}")
            return False
    
    def navigate_to_podcast(self, podcast_name):
        """Sök efter och navigera till en specifik podcast."""
        logger.info(f"Navigerar till podcast: {podcast_name}")
        try:
            # Klicka på sökrutan
            search_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='search-icon']"))
            )
            search_button.click()
            
            # Vänta på att sökrutan laddas och skriv in podcast-namnet
            search_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='search-input']"))
            )
            search_input.clear()
            search_input.send_keys(podcast_name)
            time.sleep(2)  # Vänta på sökresultat
            
            # Klicka på första podcast-resultatet
            podcast_results = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'contentSpacing')]//a[contains(@href, '/show/')]"))
            )
            
            for result in podcast_results:
                if podcast_name.lower() in result.text.lower():
                    result.click()
                    break
            else:
                logger.warning(f"Kunde inte hitta exakt matchande podcast för: {podcast_name}")
                # Klicka på första resultatet som en fallback
                if podcast_results:
                    podcast_results[0].click()
                else:
                    raise Exception("Inga podcast-resultat hittades")
            
            # Vänta på att podcast-sidan laddas
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(@class, 'Type__TypeElement')]"))
            )
            
            logger.info(f"Navigerade till podcast")
            return True
        except Exception as e:
            logger.error(f"Kunde inte navigera till podcast: {e}")
            return False
    
    def get_podcast_episodes(self, max_episodes=5):
        """Extrahera information om podcastavsnitt."""
        logger.info(f"Hämtar upp till {max_episodes} episoder")
        episodes = []
        try:
            # Vänta tills episodlistan laddas
            episode_items = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'ContentList__StyledListItem')]"))
            )
            
            # Skrolla ner för att ladda fler episoder vid behov
            if len(episode_items) < max_episodes:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                episode_items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'ContentList__StyledListItem')]")
            
            # Begränsa till max_episodes
            episode_items = episode_items[:max_episodes]
            
            for episode in episode_items:
                try:
                    # Extrahera titel
                    title_element = episode.find_element(By.XPATH, ".//a[contains(@class, 'EntityHeader')]")
                    title = title_element.text
                    link = title_element.get_attribute("href")
                    
                    # Extrahera datum
                    date = "Okänt datum"
                    try:
                        date_element = episode.find_element(By.XPATH, ".//span[contains(@class, 'Type__TypeElement') and contains(@class, 'ellipsis-one-line')]")
                        date = date_element.text
                    except:
                        pass
                    
                    # Extrahera beskrivning om tillgänglig
                    description = ""
                    try:
                        description_element = episode.find_element(By.XPATH, ".//div[contains(@class, 'LineClamp__LinesWrapper')]")
                        description = description_element.text
                    except:
                        pass
                    
                    episodes.append({
                        "title": title,
                        "date": date,
                        "link": link,
                        "description": description
                    })
                    
                except Exception as e:
                    logger.error(f"Kunde inte extrahera episod: {e}")
                    continue
                    
            logger.info(f"Hittade {len(episodes)} episoder")
            return episodes
        except Exception as e:
            logger.error(f"Kunde inte extrahera episodlista: {e}")
            return []
    
    def extract_episode_transcript(self, episode_link):
        """Försök extrahera transkript för ett avsnitt om tillgängligt."""
        logger.info(f"Försöker extrahera transkript för: {episode_link}")
        try:
            # Navigera till avsnittssidan
            self.driver.get(episode_link)
            time.sleep(3)
            
            # Kolla om det finns en "Show transcript" knapp
            transcript_button = None
            try:
                transcript_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Show transcript') or contains(text(), 'Visa transkript')]"))
                )
            except:
                logger.info("Ingen 'Show transcript'-knapp hittades")
                return None
                
            if not transcript_button:
                logger.info("Inget transkript tillgängligt för detta avsnitt")
                return None
                
            # Klicka på knappen för att visa transkript
            transcript_button.click()
            time.sleep(2)
            
            # Extrahera transkriptet
            try:
                # Försök först med den förväntade CSS-selektorn
                transcript_segments = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='transcriptSegment']"))
                )
            except:
                # Fallback till att hitta transkripttext baserat på struktur
                logger.info("Försöker alternativ metod för att hitta transkript")
                transcript_container = self.driver.find_element(By.XPATH, "//div[contains(@class, 'GenericModal__GenericModalContainer')]")
                transcript_segments = transcript_container.find_elements(By.XPATH, ".//div[contains(@class, 'Type__TypeElement')]")
            
            if not transcript_segments:
                logger.info("Kunde inte hitta transkriptsegment")
                return None
                
            transcript_text = ""
            for segment in transcript_segments:
                transcript_text += segment.text + " "
                
            logger.info(f"Extraherade transkript med längd: {len(transcript_text)} tecken")
            return transcript_text.strip()
            
        except Exception as e:
            logger.error(f"Fel vid extrahering av transkript: {e}")
            return None
    
    def analyze_transcript_for_stocks(self, transcript, podcast_name, episode_title):
        """Analysera ett transkript för omnämnanden av aktier med ChatGPT."""
        if not transcript:
            logger.warning("Inget transkript tillgängligt för analys")
            return {"error": "Inget transkript tillgängligt för analys"}
        
        try:
            logger.info("Analyserar transkript med ChatGPT API")
            
            # Begränsa transkriptet om det är för långt
            # GPT-4 har en kontextgräns, så vi begränsar till 15000 tecken för säkerhet
            if len(transcript) > 15000:
                logger.info(f"Transkriptet är för långt ({len(transcript)} tecken), begränsar till 15000 tecken")
                transcript = transcript[:15000]
            
            prompt = f"""
            Nedan följer ett transkript från podcasten "{podcast_name}" avsnittet "{episode_title}".
            
            Identifiera alla omnämnanden av aktier, börsnoterade företag eller finansiella instrument.
            För varje omnämnande, ange:
            1. Företagets/aktiens namn
            2. Sammanhanget där det nämndes (kort citat, max 100 tecken)
            3. Sentimentet (positivt, negativt, neutralt)
            4. Eventuell prisinformation eller prediktion (om det nämns)
            
            Ignorera generella diskussioner om marknaden om inga specifika aktier nämns.
            Formatera resultatet som JSON enligt följande struktur:
            {{
                "mentions": [
                    {{
                        "name": "Företagsnamn",
                        "context": "Citat från transkriptet",
                        "sentiment": "positivt/negativt/neutralt",
                        "price_info": "Eventuell prisinformation eller null"
                    }}
                ],
                "summary": "En kort sammanfattning av de viktigaste aktieomtalen"
            }}
            
            Transkript:
            {transcript}
            """
            
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Du är en finansanalytiker specialiserad på att hitta omnämnanden av aktier och börsnoterade företag i podcasttranskript. Du svarar endast med JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Analys slutförd, hittade {len(result.get('mentions', []))} aktieomtal")
            return result
            
        except Exception as e:
            logger.error(f"Fel vid analys av transkript: {e}")
            return {"error": f"Analysfel: {str(e)}"}
    
    def analyze_podcast(self, podcast_name, max_episodes=5):
        """Analysera en podcast för aktieomtal."""
        logger.info(f"Startar analys av podcast: {podcast_name}")
        
        # Skapa unik fil för att spara resultat
        result_file = os.path.join(self.results_dir, f"{podcast_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        podcast_results = {
            "podcast_name": podcast_name,
            "analysis_date": datetime.now().isoformat(),
            "episodes": []
        }
        
        try:
            # Navigera till podcast
            if not self.navigate_to_podcast(podcast_name):
                logger.error(f"Kunde inte navigera till podcast: {podcast_name}")
                return None
                
            # Hämta episoder
            episodes = self.get_podcast_episodes(max_episodes=max_episodes)
            
            # Analysera varje avsnitt
            for episode in episodes:
                logger.info(f"Analyserar avsnitt: {episode['title']}")
                
                # Extrahera transkript
                transcript = self.extract_episode_transcript(episode['link'])
                
                # Analysera beskrivning om inget transkript finns
                analysis = None
                if transcript:
                    analysis = self.analyze_transcript_for_stocks(transcript, podcast_name, episode['title'])
                else:
                    logger.info("Inget transkript hittades, analyserar beskrivning istället")
                    # Fallback till att analysera beskrivningen om den är tillräckligt lång
                    if len(episode['description']) > 100:
                        analysis = self.analyze_transcript_for_stocks(
                            f"Beskrivning: {episode['description']}", 
                            podcast_name, 
                            episode['title']
                        )
                
                episode_result = {
                    "title": episode['title'],
                    "date": episode['date'],
                    "link": episode['link'],
                    "has_transcript": transcript is not None,
                    "stock_analysis": analysis
                }
                
                podcast_results["episodes"].append(episode_result)
                
                # Spara delresultat efter varje avsnitt för att inte förlora data vid fel
                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(podcast_results, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Analys av podcast {podcast_name} slutförd")
            return podcast_results
            
        except Exception as e:
            logger.error(f"Fel vid analys av podcast: {e}")
            # Försök spara delresultat även vid fel
            if podcast_results["episodes"]:
                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(podcast_results, f, ensure_ascii=False, indent=4)
            return None
    
    def get_latest_results(self, podcast_name=None):
        """Hämta de senaste analysresultaten för en specifik podcast eller alla podcasts."""
        results = []
        
        try:
            for filename in os.listdir(self.results_dir):
                if not filename.endswith('.json'):
                    continue
                
                # Om podcast_name anges, filtrera på det
                if podcast_name and not filename.startswith(podcast_name.replace(' ', '_').lower()):
                    continue
                
                filepath = os.path.join(self.results_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    results.append(data)
            
            # Sortera efter analysdatum, nyaste först
            results.sort(key=lambda x: x.get('analysis_date', ''), reverse=True)
            
            # Om podcast_name anges, returnera bara den senaste analysen
            if podcast_name and results:
                return results[0]
            
            return results
            
        except Exception as e:
            logger.error(f"Fel vid hämtning av resultat: {e}")
            return []
    
    def get_stock_mentions(self, stock_name=None):
        """Hämta alla omnämnanden av en specifik aktie eller alla aktier."""
        try:
            all_results = self.get_latest_results()
            mentions = []
            
            for podcast in all_results:
                podcast_name = podcast.get('podcast_name', 'Okänd podcast')
                
                for episode in podcast.get('episodes', []):
                    episode_title = episode.get('title', 'Okänd episod')
                    episode_date = episode.get('date', 'Okänt datum')
                    episode_link = episode.get('link', '#')
                    
                    analysis = episode.get('stock_analysis', {})
                    if not analysis or 'error' in analysis:
                        continue
                    
                    stock_mentions = analysis.get('mentions', [])
                    
                    # Filtrera på aktienamn om det anges
                    if stock_name:
                        stock_mentions = [
                            mention for mention in stock_mentions 
                            if stock_name.lower() in mention.get('name', '').lower()
                        ]
                    
                    if stock_mentions:
                        mentions.append({
                            'podcast': podcast_name,
                            'episode': episode_title,
                            'date': episode_date,
                            'link': episode_link,
                            'mentions': stock_mentions
                        })
            
            return mentions
            
        except Exception as e:
            logger.error(f"Fel vid hämtning av aktieomtal: {e}")
            return []
    
    def run(self, podcasts_to_analyze, max_episodes_per_podcast=3):
        """Kör hela analyssprocessen för en lista av podcasts."""
        logger.info(f"Startar analys av {len(podcasts_to_analyze)} podcasts")
        
        try:
            # Konfigurera webdriver
            self.setup_driver()
            
            # Logga in på Spotify
            if not self.login_to_spotify():
                logger.error("Kunde inte logga in på Spotify. Avslutar.")
                self.driver.quit()
                return False
            
            # Analysera varje podcast
            for podcast_name in podcasts_to_analyze:
                logger.info(f"Analyserar podcast: {podcast_name}")
                self.analyze_podcast(podcast_name, max_episodes=max_episodes_per_podcast)
            
            logger.info("Analys slutförd för alla podcasts")
            return True
            
        except Exception as e:
            logger.error(f"Ett oväntat fel uppstod: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()

# Exempel på användning
if __name__ == "__main__":
    # Konfigurera med dina Spotify-inloggningsuppgifter
    scraper = PodcastScraper(
        spotify_username="din_spotify_email@exempel.se",
        spotify_password="ditt_lösenord"
    )
    
    # Lista över podcasts att analysera
    podcasts = ["Börspodden", "Fill or Kill", "Kapitalet"]
    
    # Kör analysen
    scraper.run(podcasts, max_episodes_per_podcast=2)