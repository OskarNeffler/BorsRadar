import os
import json
import time
import logging
import requests
import base64
from datetime import datetime, timedelta
import re
import hashlib
from dotenv import load_dotenv
from openai import OpenAI

# Ladda miljövariabler
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('podcast_api.log')
    ]
)

logger = logging.getLogger('podcast_api')

class PodcastAPI:
    def __init__(self, client_id=None, client_secret=None, openai_api_key=None):
        # Använd miljövariabler om inga parametrar ges
        self.client_id = client_id or os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('SPOTIFY_CLIENT_SECRET')
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        
        self.access_token = None
        self.token_expires = 0
        self.results_dir = "podcast_data"
        self.audio_dir = "podcast_audio"
        
        # Initiera OpenAI klient om API-nyckel finns
        self.client = None
        if self.openai_api_key:
            try:
                self.client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI klient initierad")
            except Exception as e:
                logger.error(f"Kunde inte initiera OpenAI: {e}")
        
        # Skapa mappar för resultat om de inte finns
        for directory in [self.results_dir, self.audio_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
            
        # Hämta access token direkt vid initiering
        self.get_access_token()
        
        # Podcast-ID mappning för direktåtkomst
        self.podcast_ids = {
            "Börspodden": "1aEkC9K5gOs3DdJnGSuE2B",
            "Nordnet Sparpodden": "1hocd5uGGPww590WCgbsb8",
            "Affärsvärlden Analys": "4zT9idqJa2cqjXaxd6Ugma",
            "Investerarens Podcast": "2RNqc3uXD4hETC4f1D66Ra",
            "Nextconomy by Danske Bank Sweden": "7BJcSnEs8jSgtqxifh0IGx",
            "Börsmäklarna": "2ZNderpSclbX2NkNt1lQEm",
            "Tillsammans mot miljonen": "04MTmjO2aeiO6503EW7nrI"
        }
    
    def get_access_token(self):
        """Hämta access token från Spotify API."""
        if self.access_token and time.time() < self.token_expires - 60:
            # Token är fortfarande giltig
            return self.access_token
        
        logger.info("Hämtar ny access token från Spotify API")
        
        try:
            # Koda client_id och client_secret enligt Spotify API spec
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {'grant_type': 'client_credentials'}
            
            response = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=data)
            response.raise_for_status()  # Raise exception för HTTP-fel
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.token_expires = time.time() + token_data['expires_in']
            
            logger.info(f"Ny access token erhållen, giltig i {token_data['expires_in']} sekunder")
            return self.access_token
            
        except Exception as e:
            logger.error(f"Fel vid hämtning av access token: {e}")
            raise
    
    def get_podcast_id(self, podcast_name):
        """Hämta podcast-ID från namn."""
        # Kontrollera om podcasten finns i mappningen
        if podcast_name in self.podcast_ids:
            return self.podcast_ids[podcast_name]
        
        # Annars, sök efter podcasten
        try:
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}'
            }
            
            # Encode-säkra söktermen
            safe_name = requests.utils.quote(podcast_name)
            
            # Sök efter podcasten
            search_url = f'https://api.spotify.com/v1/search?q={safe_name}&type=show&market=SE&limit=5'
            response = requests.get(search_url, headers=headers)
            response.raise_for_status()
            
            search_results = response.json()
            
            if 'shows' in search_results and 'items' in search_results['shows'] and search_results['shows']['items']:
                # Hitta den podcast som bäst matchar söktermen
                best_match = None
                
                for show in search_results['shows']['items']:
                    if podcast_name.lower() in show['name'].lower():
                        best_match = show
                        break
                
                # Om ingen exakt matchning, använd första resultatet
                if not best_match and search_results['shows']['items']:
                    best_match = search_results['shows']['items'][0]
                
                if best_match:
                    logger.info(f"Hittade podcast: {best_match['name']} (ID: {best_match['id']})")
                    return best_match['id']
            
            logger.warning(f"Kunde inte hitta podcast: {podcast_name}")
            return None
            
        except Exception as e:
            logger.error(f"Fel vid sökning efter podcast: {e}")
            return None
    
    def generate_episode_id(self, episode_data):
        """Generera ett unikt ID för ett avsnitt för framtida databaslagring"""
        episode_key = f"{episode_data['id']}_{episode_data['release_date']}"
        return hashlib.md5(episode_key.encode()).hexdigest()
    
    def get_podcast_by_id(self, podcast_id):
        """Hämta podcast-information med ID."""
        logger.info(f"Hämtar podcast med ID: {podcast_id}")
        
        try:
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}'
            }
            
            show_url = f'https://api.spotify.com/v1/shows/{podcast_id}?market=SE'
            response = requests.get(show_url, headers=headers)
            response.raise_for_status()
            
            podcast_info = response.json()
            logger.info(f"Hämtade podcast: {podcast_info['name']}")
            
            return podcast_info
            
        except Exception as e:
            logger.error(f"Fel vid hämtning av podcast med ID {podcast_id}: {e}")
            return None
    
    def get_podcast_episodes(self, podcast_id, max_episodes=5):
        """Hämta episoder för en podcast med Spotify API."""
        logger.info(f"Hämtar upp till {max_episodes} episoder för podcast ID: {podcast_id}")
        
        try:
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}'
            }
            
            # Hämta episoder
            episodes_url = f'https://api.spotify.com/v1/shows/{podcast_id}/episodes?market=SE&limit={max_episodes}'
            response = requests.get(episodes_url, headers=headers)
            response.raise_for_status()
            
            episodes_data = response.json()
            
            if 'items' in episodes_data and episodes_data['items']:
                logger.info(f"Hittade {len(episodes_data['items'])} episoder")
                return episodes_data['items']
            else:
                logger.warning(f"Inga episoder hittades för podcast ID: {podcast_id}")
                return []
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av episoder för podcast ID {podcast_id}: {e}")
            return []
    
    def get_multiple_podcasts(self, podcast_ids):
        """Hämta information om flera podcasts på en gång."""
        logger.info(f"Hämtar information om {len(podcast_ids)} podcasts")
        
        try:
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}'
            }
            
            # Formatera ID-strängen
            ids_string = ",".join(podcast_ids)
            
            # Hämta podcasts
            shows_url = f'https://api.spotify.com/v1/shows?market=SE&ids={ids_string}'
            response = requests.get(shows_url, headers=headers)
            response.raise_for_status()
            
            shows_data = response.json()
            
            if 'shows' in shows_data and shows_data['shows']:
                logger.info(f"Hämtade information om {len(shows_data['shows'])} podcasts")
                return shows_data['shows']
            else:
                logger.warning("Inga podcasts hittades")
                return []
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av podcasts: {e}")
            return []
    
    def download_audio_preview(self, episode):
        """Ladda ner audio preview för en episod om tillgänglig."""
        if not episode.get('audio_preview_url'):
            logger.warning(f"Ingen ljudförhandsgranskning tillgänglig för episod: {episode.get('name')}")
            return None
            
        try:
            audio_url = episode['audio_preview_url']
            episode_id = episode['id']
            
            # Skapa sökväg för filen
            audio_path = os.path.join(self.audio_dir, f"{episode_id}.mp3")
            
            # Kontrollera om filen redan finns
            if os.path.exists(audio_path):
                logger.info(f"Ljudfil finns redan för episod: {episode.get('name')}")
                return audio_path
                
            # Ladda ner filen
            logger.info(f"Laddar ner ljudförhandsgranskning för episod: {episode.get('name')}")
            response = requests.get(audio_url, stream=True)
            response.raise_for_status()
            
            with open(audio_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logger.info(f"Ljudförhandsgranskning sparad till: {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Fel vid nedladdning av ljudförhandsgranskning: {e}")
            return None
    
    def transcribe_audio(self, audio_path):
        """Transkribera ljudfil med OpenAI Whisper API."""
        if not self.client:
            logger.error("OpenAI klient är inte initierad, kan inte transkribera ljud")
            return None
            
        if not audio_path or not os.path.exists(audio_path):
            logger.error(f"Ljudfil hittades inte: {audio_path}")
            return None
            
        try:
            logger.info(f"Transkriberar ljudfil: {audio_path}")
            
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
                
            logger.info(f"Transkription klar, längd: {len(transcript.text)} tecken")
            return transcript.text
            
        except Exception as e:
            logger.error(f"Fel vid transkribering av ljud: {e}")
            return None
    
    def is_episode_already_transcribed(self, episode_id):
        """Kontrollera om ett avsnitt redan har transkriberats"""
        # Kontrollera om ljudfilen finns
        audio_path = os.path.join(self.audio_dir, f"{episode_id}.mp3")
        if not os.path.exists(audio_path):
            return False
            
        # Kontrollera om transkriptet finns i något av resultaten
        for filename in os.listdir(self.results_dir):
            if not filename.endswith('.json'):
                continue
                
            filepath = os.path.join(self.results_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for episode in data.get('episodes', []):
                        if episode.get('id') == episode_id and episode.get('transcript'):
                            return True
            except:
                continue
                
        return False
    
    def summarize_with_gpt(self, text, podcast_name, episode_title):
        """Sammanfatta text med GPT-modell och hitta aktieomtal."""
        if not self.client:
            logger.error("OpenAI klient är inte initierad, kan inte sammanfatta text")
            return None
            
        if not text:
            logger.warning("Ingen text att sammanfatta")
            return None
            
        try:
            logger.info(f"Sammanfattar text för episod: {episode_title}")
            
            # Begränsa textlängden vid behov
            if len(text) > 15000:
                logger.info(f"Texten är för lång ({len(text)} tecken), begränsar till 15000 tecken")
                text = text[:15000]
            
            prompt = f"""
            Här är ett transkript från podcasten "{podcast_name}", avsnittet "{episode_title}".
            
            Gör följande baserat på detta transkript:
            1. Skriv en kort sammanfattning av innehållet (3-5 meningar)
            2. Identifiera alla omnämnanden av aktier, börsnoterade företag eller finansiella instrument
            3. För varje omnämnande, ange:
               - Företagets/aktiens namn
               - Sammanhanget där det nämndes (kort citat)
               - Sentimentet (positivt, negativt, neutralt)
               - Eventuell prisinformation eller prediktion (om det nämns)
            
            Formattera resultatet som JSON enligt följande struktur:
            {{
                "summary": "En sammanfattande text",
                "mentions": [
                    {{
                        "name": "Företagsnamn",
                        "context": "Citat från texten",
                        "sentiment": "positivt/negativt/neutralt",
                        "price_info": "Eventuell prisinformation eller null"
                    }}
                ]
            }}
            
            Transkript:
            {text}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Du är en finansanalytiker specialiserad på att sammanfatta poddar och hitta omnämnanden av aktier och börsnoterade företag. Du svarar endast med JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            try:
                result = json.loads(response.choices[0].message.content)
                logger.info(f"Sammanfattning klar, hittade {len(result.get('mentions', []))} aktieomtal")
                return result
            except json.JSONDecodeError:
                logger.error("Kunde inte tolka svar från GPT som JSON")
                return {
                    "summary": "Kunde inte skapa sammanfattning",
                    "mentions": []
                }
            
        except Exception as e:
            logger.error(f"Fel vid sammanfattning av text: {e}")
            return {
                "summary": "Fel vid sammanfattning",
                "mentions": []
            }
    
    def analyze_description_for_stocks(self, description, podcast_name, episode_title, use_openai=True):
        """Analysera en beskrivning för omnämnanden av aktier med egen implementation eller OpenAI."""
        if not description:
            logger.warning("Ingen beskrivning tillgänglig för analys")
            return {"error": "Ingen beskrivning tillgänglig för analys"}
        
        # Om OpenAI klient finns och use_openai är True, använd den
        if self.client and use_openai:
            return self.summarize_with_gpt(description, podcast_name, episode_title)
        
        # Annars använd egen implementation
        try:
            logger.info("Analyserar beskrivning med egen algoritm")
            
            # Begränsa beskrivningen om den är för lång
            if len(description) > 10000:
                logger.info(f"Beskrivningen är för lång ({len(description)} tecken), begränsar till 10000 tecken")
                description = description[:10000]
            
            # Lista på svenska börsbolag att söka efter - utökad
            companies = [
                # Svenska storbolag med varianter
                "Volvo", "Volvo Group", "Volvoaktien", "Volvobil", 
                "Ericsson", "Ericsson B", "Ericssonaktien", 
                "H&M", "Hennes & Mauritz", "HM", "H och M",
                "SEB", "Skandinaviska Enskilda Banken", 
                "Handelsbanken", "SHB", 
                "Investor", "Investor AB", "Investor B",
                "Atlas Copco", "Atlas", 
                "Swedbank", 
                "Telia", "Telia Company", "Teliaaktien",
                "Nordea", "Nordeaaktien",
                "Electrolux", "Electrolux Group", 
                "Skanska", "Skanska AB", 
                "ICA", "ICA Gruppen", 
                "IKEA", 
                "SAS", "SAS Group", 
                "Spotify", "Spotifyaktien",
                "Kinnevik", "Kinnevik AB",
                "Hexagon", "Hexagon AB",
                "Sandvik", "Sandvik AB",
                "Securitas", "Securitas AB",
                "ABB", "ABB Ltd", 
                "Axfood", "Axfood AB",
                
                # Andra populära bolag
                "EQT", "EQT AB", 
                "Evolution", "Evolution Gaming", "Evo", 
                "Embracer", "Embracer Group", 
                "Sinch", "Sinch AB", 
                "SSAB", "SSAB AB", 
                "Boliden", "Boliden AB", 
                "Alfa Laval", 
                "Tele2", "Tele2 AB", 
                "Balder", "Fastighets Balder", 
                "Castellum", "Castellum AB", 
                "Assa Abloy", "ASSA", 
                "Swedish Match", 
                "Lundin", "Lundin Energy", "Lundin Mining", 
                "Getinge", "Getinge AB", 
                "SKF", "SKF AB", 
                "Epiroc", "Epiroc AB", 
                "Nibe", "NIBE", "Nibe Industrier", 
                "Industrivärden", "Industrivärden AB", 
                "Husqvarna", "Husqvarna AB",
                
                # Amerikanska bolag
                "Microsoft", "MSFT", 
                "Apple", "AAPL", 
                "Amazon", "AMZN", 
                "Google", "Alphabet", "GOOGL", 
                "Tesla", "TSLA", 
                "Meta", "Facebook", "FB", 
                "Nvidia", "NVDA", 
                "Intel", "INTC", 
                
                # Övriga internationella bolag
                "Samsung", 
                "Sony", 
                "LVMH", 
                "Nike", "NKE", 
                "Adidas", 
                "BYD", 
                "AstraZeneca", 
                "Moderna", "MRNA"
            ]
            
            # Positiva och negativa ord för sentiment-analys
            positive_words = [
                "uppgång", "ökning", "stiger", "positivt", "potential", "rekommenderar", "tillväxt",
                "stark", "bra", "lyckad", "framgång", "imponerande", "överträffar", "överstiger",
                "förbättring", "höjdpunkt", "framtida", "förväntningar", "möjlighet", "intressant"
            ]
            
            negative_words = [
                "nedgång", "minskning", "sjunker", "negativt", "risk", "problem", "varnar",
                "svag", "dålig", "misslyckad", "motgång", "besvikelse", "underpresterar", "missar",
                "försämring", "lågpunkt", "problem", "oro", "osäkerhet", "risk", "kritisk"
            ]
            
            # Hitta aktieomtal
            mentions = []
            description_lower = description.lower()
            
            for company in companies:
                company_lower = company.lower()
                if company_lower in description_lower:
                    # Hitta alla förekomster
                    start_positions = [m.start() for m in re.finditer(re.escape(company_lower), description_lower)]
                    
                    for pos in start_positions:
                        # Extrahera kontext runt omnämnandet (50 tecken före och efter)
                        start = max(0, pos - 50)
                        end = min(len(description), pos + len(company) + 50)
                        context = description[start:end].strip()
                        
                        # Enkel sentiment-analys
                        sentiment = "neutralt"
                        context_lower = context.lower()
                        
                        positive_score = sum(1 for word in positive_words if word.lower() in context_lower)
                        negative_score = sum(1 for word in negative_words if word.lower() in context_lower)
                        
                        if positive_score > negative_score:
                            sentiment = "positivt"
                        elif negative_score > positive_score:
                            sentiment = "negativt"
                        
                        # Leta efter prisinformation med regex
                        price_info = None
                        price_patterns = [
                            r'\d+[,.]?\d*\s*(kr|kronor|SEK|USD|\$|€|EUR)',
                            r'(pris|kurs|aktie).*?(\d+[,.]?\d*)',
                            r'(\d+[,.]?\d*)\s*%'
                        ]
                        
                        for pattern in price_patterns:
                            price_match = re.search(pattern, context_lower)
                            if price_match:
                                price_info = price_match.group(0)
                                break
                        
                        # Lägg till omnämnandet
                        mentions.append({
                            "name": company,
                            "context": context,
                            "sentiment": sentiment,
                            "price_info": price_info
                        })
            
            # Ta bort eventuella duplicerade omnämnanden baserat på kontext
            unique_mentions = []
            seen_contexts = set()
            
            for mention in mentions:
                if mention["context"] not in seen_contexts:
                    seen_contexts.add(mention["context"])
                    unique_mentions.append(mention)
            
            result = {
                "summary": f"Hittade {len(unique_mentions)} aktieomtal i beskrivningen.",
                "mentions": unique_mentions
            }
            
            logger.info(f"Analys slutförd, hittade {len(unique_mentions)} aktieomtal")
            return result
            
        except Exception as e:
            logger.error(f"Fel vid analys av beskrivning: {e}")
            return {"error": f"Analysfel: {str(e)}"}
    
    def save_to_file(self, podcast_name, episodes_with_analysis):
        """Spara analysresultat till JSON-fil."""
        try:
            result_file = os.path.join(self.results_dir, f"{podcast_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            result_data = {
                "podcast_name": podcast_name,
                "analysis_date": datetime.now().isoformat(),
                "episodes": episodes_with_analysis
            }
            
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=4)
                
            logger.info(f"Sparade analysresultat för {podcast_name} i JSON-fil: {result_file}")
            return result_file
        except Exception as e:
            logger.error(f"Fel vid lagring av resultat: {e}")
            return None
    
    def analyze_single_episode(self, episode, avoid_transcription=False):
        """Analysera ett enskilt avsnitt för aktieomtal."""
        try:
            episode_id = episode['id']
            episode_title = episode['name']
            episode_description = episode['description']
            episode_date = episode['release_date']
            episode_link = episode['external_urls']['spotify']
            
            # Generera ett unikt ID för framtida databaslagring
            unique_id = self.generate_episode_id(episode)
            
            logger.info(f"Analyserar avsnitt: {episode_title}")
            
            # Kontrollera om avsnittet redan har transkriberats
            already_transcribed = self.is_episode_already_transcribed(episode_id)
            
            # Försök hämta och transkribera audio preview om den inte redan är transkriberad
            audio_path = None
            transcript = None
            
            if not avoid_transcription and not already_transcribed:
                audio_path = self.download_audio_preview(episode)
                if audio_path:
                    transcript = self.transcribe_audio(audio_path)
            
            # Analysera transkript om det finns, annars beskrivning
            analysis = None
            has_transcript = transcript is not None
            
            if transcript and self.client:
                logger.info("Analyserar transkript med GPT")
                analysis = self.summarize_with_gpt(transcript, episode_title, episode_title)
            else:
                logger.info("Använder lokal analys eller beskrivning")
                if episode_description:
                    analysis = self.analyze_description_for_stocks(
                        episode_description, 
                        episode_title, 
                        episode_title,
                        use_openai=(self.client is not None and not avoid_transcription)
                    )
                else:
                    logger.warning("Ingen beskrivning tillgänglig för analys")
            
            episode_result = {
                "id": unique_id,
                "title": episode_title,
                "date": episode_date,
                "link": episode_link,
                "description": episode_description,
                "transcript": transcript,
                "has_transcript": has_transcript,
                "stock_analysis": analysis
            }
            
            return episode_result
            
        except Exception as e:
            logger.error(f"Fel vid analys av avsnitt: {e}")
            return None
    
    def analyze_podcast(self, podcast_name, episodes=None, max_episodes=5, avoid_transcription=False):
        """Analysera en podcast för aktieomtal."""
        logger.info(f"Startar analys av podcast: {podcast_name}")
        
        podcast_results = {
            "podcast_name": podcast_name,
            "analysis_date": datetime.now().isoformat(),
            "episodes": []
        }
        
        try:
            # Hitta podcast-ID
            podcast_id = None
            if podcast_name in self.podcast_ids:
                podcast_id = self.podcast_ids[podcast_name]
            else:
                podcast_id = self.get_podcast_id(podcast_name)
                
            if not podcast_id:
                logger.error(f"Kunde inte hitta podcast-ID för: {podcast_name}")
                return None
            
            # Hämta podcast-information
            podcast = self.get_podcast_by_id(podcast_id)
            if not podcast:
                logger.error(f"Kunde inte hämta podcast: {podcast_name}")
                return None
            
            podcast_name = podcast['name']  # Använd det faktiska namnet från Spotify
            
            # Skapa unik fil för att spara resultat
            result_file = os.path.join(self.results_dir, f"{podcast_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
            # Använd de givna episoderna eller hämta nya
            if episodes is None:
                episodes = self.get_podcast_episodes(podcast_id, max_episodes=max_episodes)
            
            # Analysera varje avsnitt
            for episode in episodes:
                # Analysera avsnittet
                episode_result = self.analyze_single_episode(episode, avoid_transcription=avoid_transcription)
                
                if episode_result:
                    podcast_results["episodes"].append(episode_result)
                    
                    # Spara delresultat efter varje avsnitt för att inte förlora data vid fel
                    with open(result_file, "w", encoding="utf-8") as f:
                        json.dump(podcast_results, f, ensure_ascii=False, indent=4)
            
            # Spara slutresultat
            saved_file = self.save_to_file(podcast_name, podcast_results["episodes"])
            
            logger.info(f"Analys av podcast {podcast_name} slutförd, resultat sparade i {saved_file}")
            return podcast_results
            
        except Exception as e:
            logger.error(f"Fel vid analys av podcast: {e}")
            # Försök spara delresultat även vid fel
            if podcast_results["episodes"]:
                self.save_to_file(podcast_name, podcast_results["episodes"])
            return None
    
    def check_new_episodes(self, days=14):
        """Kontrollera om det finns nya avsnitt sedan senaste analysen."""
        logger.info(f"Kontrollerar nya avsnitt de senaste {days} dagarna")
        
        new_episodes = {}
        
        try:
            # Beräkna datum för days dagar sedan
            check_date = datetime.now() - timedelta(days=days)
            check_date_str = check_date.strftime("%Y-%m-%d")
            
            # Gå igenom alla podcast-ID
            for podcast_name, podcast_id in self.podcast_ids.items():
                # Hämta senaste analysen för denna podcast
                latest_analysis = self.get_latest_results(podcast_name)
                
                # Hämta de senaste avsnitten
                episodes = self.get_podcast_episodes(podcast_id, max_episodes=10)
                
                # Filtrera avsnitt efter datum
                recent_episodes = []
                for episode in episodes:
                    if episode['release_date'] >= check_date_str:
                        # Kontrollera om avsnittet redan är analyserat
                        is_analyzed = False
                        if latest_analysis:
                            for analyzed_episode in latest_analysis.get('episodes', []):
                                if analyzed_episode.get('id') == self.generate_episode_id(episode):
                                    is_analyzed = True
                                    break
                                    
                        if not is_analyzed:
                            recent_episodes.append({
                                'id': episode['id'],
                                'title': episode['name'],
                                'date': episode['release_date'],
                                'link': episode['external_urls']['spotify']
                            })
                
                if recent_episodes:
                    new_episodes[podcast_name] = recent_episodes
            
            return new_episodes
            
        except Exception as e:
            logger.error(f"Fel vid kontroll av nya avsnitt: {e}")
            return {}
    
    def get_latest_results(self, podcast_name=None):
        """Hämta de senaste analysresultaten från filsystemet"""
        return self._get_latest_results_from_files(podcast_name)
    
    def _get_latest_results_from_files(self, podcast_name=None):
        """Metod för att hämta resultat från filsystemet"""
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
            logger.error(f"Fel vid hämtning av resultat från filer: {e}")
            return []
    
    def get_stock_mentions(self, stock_name=None):
        """Hämta alla omnämnanden av en specifik aktie från JSON-filerna"""
        try:
            all_results = self._get_latest_results_from_files()
            mentions = []
            
            for podcast_data in all_results:
                podcast_name = podcast_data.get('podcast_name', 'Okänd podcast')
                
                for episode in podcast_data.get('episodes', []):
                    title = episode.get('title', 'Okänd episod')
                    date = episode.get('date', 'Okänt datum')
                    link = episode.get('link', '')
                    episode_id = episode.get('id', '')
                    
                    stock_analysis = episode.get('stock_analysis', {})
                    episode_mentions = stock_analysis.get('mentions', [])
                    
                    # Filtrera på aktienamn om specificerat
                    if stock_name:
                        episode_mentions = [m for m in episode_mentions if stock_name.lower() in m.get('name', '').lower()]
                    
                    if episode_mentions:
                        mentions.append({
                            'podcast': podcast_name,
                            'episode': title,
                            'episode_id': episode_id,
                            'date': date,
                            'link': link,
                            'mentions': episode_mentions,
                            'summary': stock_analysis.get('summary', '')
                        })
            
            return mentions
                
        except Exception as e:
            logger.error(f"Fel vid hämtning av aktieomtal: {e}")
            return []