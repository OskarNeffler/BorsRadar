#!/usr/bin/env python3
import os
import sys
import json
import logging
import argparse
import re
import time
import tempfile
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Optional, Any

# External libraries
import requests
import yt_dlp
import google.generativeai as genai
from googleapiclient.discovery import build
from dotenv import load_dotenv
import pandas as pd
import colorama
from colorama import Fore, Style
from bs4 import BeautifulSoup
import psycopg2
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Initialize colorama for colored output
colorama.init()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('youtube_podcast_analyzer.log')
    ]
)
logger = logging.getLogger('youtube_podcast_analyzer')

class YouTubePodcastAnalyzer:
    def __init__(self, youtube_api_key=None, google_api_key=None, data_dir='podcast_data', db_url=None):
        """
        Initialize YouTube Podcast Analyzer

        :param youtube_api_key: YouTube Data API v3 key (optional)
        :param google_api_key: Google API key for Gemini (optional)
        :param data_dir: Directory to save analysis results
        :param db_url: Database connection URL (optional)
        """
        # Configuration
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, 'transcripts'), exist_ok=True)

        # Database connection
        self.db_engine = None
        self.db_session = None
        if db_url:
            try:
                from models import Base
                from sqlalchemy.orm import sessionmaker, scoped_session
                
                # Skapa engine
                self.db_engine = create_engine(db_url)
                
                # Skapa alla tabeller
                Base.metadata.create_all(self.db_engine)
                
                # Skapa en sessionsfabrik med scoped_session
                session_factory = sessionmaker(bind=self.db_engine)
                self.db_session = scoped_session(session_factory)
                
                logger.info("Database connection and session established successfully")
            except Exception as e:
                logger.error(f"Error establishing database connection: {e}")
                self.db_engine = None
                self.db_session = None

        # API clients (initialize only if keys are provided)
        self.youtube = None
        if youtube_api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=youtube_api_key)
                logger.info("YouTube API client initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing YouTube API client: {e}")

        # Save Google API key
        self.google_api_key = google_api_key

        # Podcast playlists - these are hardcoded since they remain the same
        self.podcasts = {
            'Avanzapodden': 'PLbBkvdCCY_gsmZi4wIBLq7wy1MIRhQhUO',
            'Nordnet Sparpodden': 'PLmApuroM5knKuqEWo-uTZObynsen8EZnJ',
            'Börssnurr': 'PL-aXa0lr5q4W46DffCgkMDBmmpsPDa4qK'
        }

        # No manual transcripts - we'll fetch them dynamically
        self.manual_transcripts = {}

    
    def extract_transcript_from_html(self, html_content, video_id):
        """
        Extract transcript from the YouTubeToTranscript HTML content
        
        :param html_content: HTML content from the transcript page
        :param video_id: YouTube video ID (for saving the transcript)
        :return: Transcript text or None
        """
        try:
            # Save the full HTML for debugging
            debug_path = os.path.join(self.data_dir, 'transcripts', f'{video_id}_debug.html')
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Method 1: Find transcript segments (as seen in the provided example)
            transcript_segments = soup.find_all('span', class_='transcript-segment')
            if transcript_segments and len(transcript_segments) > 5:  # At least some meaningful content
                # Join all transcript segments
                transcript_text = " ".join([segment.get_text().strip() for segment in transcript_segments])
                print(f"{Fore.GREEN}Found {len(transcript_segments)} transcript segments{Style.RESET_ALL}")
                return transcript_text
            
            # Method 2: Look for the transcript container
            transcript_container = soup.find('p', class_='inline NA text-primary-content')
            if transcript_container:
                transcript_text = transcript_container.get_text(separator=' ', strip=True)
                print(f"{Fore.GREEN}Found transcript in container{Style.RESET_ALL}")
                return transcript_text
            
            # Method 3: Look for any div with transcript data
            transcript_divs = soup.find_all('div', id=lambda x: x and 'transcript' in x.lower())
            for div in transcript_divs:
                transcript_text = div.get_text(separator=' ', strip=True)
                if len(transcript_text) > 500:  # Reasonable transcript length
                    print(f"{Fore.GREEN}Found transcript in div with ID containing 'transcript'{Style.RESET_ALL}")
                    return transcript_text
            
            # Method 4: Look for common Swedish podcast starting phrases in the text
            page_text = soup.get_text()
            swedish_markers = [
                "dags för ett nytt avsnitt", 
                "hej och välkommen", 
                "välkomna till", 
                "välkommen tillbaka", 
                "hej allihopa",
                "hej på er"
            ]
            
            for marker in swedish_markers:
                if marker in page_text.lower():
                    start_idx = page_text.lower().find(marker)
                    if start_idx > -1:
                        # Get a large chunk of text starting from the marker
                        extracted_text = page_text[start_idx:start_idx + 100000]
                        print(f"{Fore.GREEN}Found transcript starting with '{marker}'!{Style.RESET_ALL}")
                        return extracted_text
            
            # Method 5: Look for any large text block that might be the transcript
            # Find all text blocks (paragraphs, divs, etc.) and check their length
            text_blocks = []
            for tag in soup.find_all(['p', 'div', 'section']):
                text = tag.get_text(separator=' ', strip=True)
                if len(text) > 1000:  # Minimum length for a transcript
                    text_blocks.append(text)
            
            if text_blocks:
                # Use the longest text block
                longest_block = max(text_blocks, key=len)
                print(f"{Fore.GREEN}Found a large text block that might be the transcript ({len(longest_block)} chars){Style.RESET_ALL}")
                return longest_block
            
            # Method 6: Last resort - just use the full page text if it's substantial
            full_text = soup.get_text(separator=' ', strip=True)
            if len(full_text) > 2000:  # Minimum length for a transcript
                print(f"{Fore.YELLOW}Using full page text as transcript ({len(full_text)} chars){Style.RESET_ALL}")
                return full_text
            
            logger.warning("Could not find transcript in the HTML content")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting transcript from HTML: {e}")
            return None
    def get_transcript_from_website(self, video_url):
        transcript_methods = [
            self._method_youtubetotranscript,
            self._method_alternative_transcript,
            self._method_youtube_description
        ]
        
        for method in transcript_methods:
            try:
                transcript = method(video_url)
                if transcript and len(transcript) > 100:
                    return transcript
            except Exception as e:
                logger.warning(f"Transcript method {method.__name__} failed: {e}")
        
        return None

    def _method_youtubetotranscript(self, video_url):
        """
        Get transcript from YouTubeToTranscript.com
        
        :param video_url: YouTube video URL
        :return: Transcript text or None
        """
        try:
            print(f"{Fore.CYAN}Fetching transcript from YouTubeToTranscript.com for: {video_url}{Style.RESET_ALL}")
            
            # Extract video ID from URL
            video_id = None
            if 'youtube.com/watch?v=' in video_url:
                video_id = video_url.split('watch?v=')[1].split('&')[0]
            elif 'youtu.be/' in video_url:
                video_id = video_url.split('youtu.be/')[1].split('?')[0]
            
            if not video_id:
                logger.warning(f"Could not extract video ID from URL: {video_url}")
                return None
            
            # Check if we already have a transcript file
            transcript_path = os.path.join(self.data_dir, 'transcripts', f'{video_id}.txt')
            if os.path.exists(transcript_path):
                print(f"{Fore.GREEN}Using existing transcript file for video ID: {video_id}{Style.RESET_ALL}")
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            # Set up a session with browser-like headers
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://youtubetotranscript.com/',
                'Origin': 'https://youtubetotranscript.com',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
            }
            
            # Load the main page first to get cookies
            main_page = session.get('https://youtubetotranscript.com/', headers=headers)
            if main_page.status_code != 200:
                logger.warning(f"Failed to load main page. Status code: {main_page.status_code}")
            
            # Prepare form data to submit the YouTube URL
            form_data = {
                'youtube_url': video_url
            }
            
            # Submit the form to get the transcript
            response = session.post(
                'https://youtubetotranscript.com/transcript',
                headers=headers,
                data=form_data,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch transcript page. Status code: {response.status_code}")
                return None
            
            # Extract transcript from HTML
            transcript_text = self.extract_transcript_from_html(response.text, video_id)
            
            # If transcript not found, try alternative URL format
            if not transcript_text:
                print(f"{Fore.YELLOW}First attempt failed. Trying alternative method...{Style.RESET_ALL}")
                transcript_url = f"https://youtubetotranscript.com/transcript?v={video_id}"
                direct_response = session.get(transcript_url, headers=headers)
                
                if direct_response.status_code == 200:
                    transcript_text = self.extract_transcript_from_html(direct_response.text, video_id)
            
            # If still not found, try one more method - simulate manual entry
            if not transcript_text:
                print(f"{Fore.YELLOW}Second attempt failed. Trying one more method...{Style.RESET_ALL}")
                # Wait a bit before trying again
                time.sleep(2)
                
                # Try to directly access the transcript page
                direct_url = f'https://youtubetotranscript.com/transcript'
                params = {'v': video_id}
                try:
                    direct_response = session.get(direct_url, params=params, headers=headers)
                    if direct_response.status_code == 200:
                        transcript_text = self.extract_transcript_from_html(direct_response.text, video_id)
                except Exception as e:
                    logger.error(f"Error in third attempt: {e}")
            
            if transcript_text:
                # Save transcript to file for future use
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(transcript_text)
                return transcript_text
            else:
                print(f"{Fore.RED}Could not extract transcript after multiple attempts{Style.RESET_ALL}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting transcript from website: {e}")
            return None
    
    def _method_alternative_transcript(self, video_url):
        """
        Alternativ metod för att hämta transkript med yt-dlp
        """
        try:
            import yt_dlp
            
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['sv', 'en'],
                'skip_download': True,
                'outtmpl': os.path.join(self.data_dir, 'transcripts', '%(id)s.%(ext)s')
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(video_url, download=False)
                video_id = info_dict.get('id', None)
                
                if video_id:
                    # Försök hitta svenska eller engelska undertexter
                    for lang in ['sv', 'en']:
                        subtitle_file = os.path.join(
                            self.data_dir, 
                            'transcripts', 
                            f'{video_id}.{lang}.vtt'
                        )
                        
                        if os.path.exists(subtitle_file):
                            with open(subtitle_file, 'r', encoding='utf-8') as f:
                                return f.read()
            
            return None
        except Exception as e:
            logger.warning(f"Alternative transcript method failed: {e}")
            return None

    def _method_youtube_description(self, video_url):
        """
        Fallback-metod som hämtar och analyserar videobeskrivningen
        """
        try:
            video_info = self.get_video_info(video_url)
            description = video_info.get('description', '')
            
            if description and len(description) > 200:
                logger.info("Using video description as transcript fallback")
                return description
            
            return None
        except Exception as e:
            logger.warning(f"YouTube description method failed: {e}")
            return None

    def get_video_info(self, video_url):
        """
        Get video information using YouTube API
        
        :param video_url: YouTube video URL
        :return: Dictionary with video information
        """
        try:
            # Extract video ID from URL
            video_id = None
            if 'youtube.com/watch?v=' in video_url:
                video_id = video_url.split('watch?v=')[1].split('&')[0]
            elif 'youtu.be/' in video_url:
                video_id = video_url.split('youtu.be/')[1].split('?')[0]
            
            if not video_id:
                logger.warning(f"Could not extract video ID from URL: {video_url}")
                return {
                    'title': 'Unknown',
                    'video_id': 'Unknown',
                    'video_url': video_url,
                    'published_at': 'Unknown',
                    'description': ''
                }
            
            # Check if we have YouTube API access
            if self.youtube:
                try:
                    request = self.youtube.videos().list(
                        part="snippet",
                        id=video_id
                    )
                    response = request.execute()
                    
                    if response.get('items'):
                        snippet = response['items'][0]['snippet']
                        return {
                            'title': snippet.get('title', 'Unknown'),
                            'video_id': video_id,
                            'video_url': video_url,
                            'published_at': snippet.get('publishedAt', 'Unknown'),
                            'description': snippet.get('description', '')
                        }
                except Exception as e:
                    logger.warning(f"YouTube API error: {e}")
            
            # Fallback to basic info if YouTube API failed or not available
            logger.info(f"Using basic info for video {video_id} (YouTube API not available)")
            return {
                'title': f"Video {video_id}",
                'video_id': video_id,
                'video_url': video_url,
                'published_at': 'Unknown',
                'description': ''
            }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return {
                'title': 'Unknown',
                'video_id': video_id if video_id else 'Unknown',
                'video_url': video_url,
                'published_at': 'Unknown',
                'description': ''
            }
    def has_analyzed_video(self, video_id):
        """
        Check if a video has already been analyzed
        
        :param video_id: YouTube video ID
        :return: Boolean indicating if the video has been analyzed
        """
        try:
            # Sök igenom alla JSON-filer i data-katalogen
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.data_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # Kolla om video_id finns i någon analys
                            for item in data.get('items', []):
                                if item.get('video_id') == video_id:
                                    logger.info(f"Video {video_id} already analyzed in {filename}")
                                    return True
                    except Exception as e:
                        logger.warning(f"Could not check file {filename}: {e}")
            
            return False
        except Exception as e:
            logger.error(f"Error checking for existing analyses: {e}")
            return False

    def get_playlist_videos(self, playlist_id_or_url, max_videos=5):
        """
        Get videos from a YouTube playlist using YouTube API
        
        :param playlist_id_or_url: YouTube playlist ID or URL
        :param max_videos: Maximum number of videos to get
        :return: List of video URLs
        """
        try:
            # Extract playlist ID if URL is provided
            playlist_id = playlist_id_or_url
            if 'youtube.com/playlist' in playlist_id_or_url:
                if 'list=' in playlist_id_or_url:
                    playlist_id = playlist_id_or_url.split('list=')[1].split('&')[0]
            
            # Check if we have YouTube API access
            if self.youtube:
                try:
                    videos = []
                    next_page_token = None
                    
                    while len(videos) < max_videos:
                        # Get playlist items
                        request = self.youtube.playlistItems().list(
                            part="contentDetails",
                            playlistId=playlist_id,
                            maxResults=min(50, max_videos - len(videos)),
                            pageToken=next_page_token
                        )
                        response = request.execute()
                        
                        # Extract video IDs and create URLs
                        for item in response.get('items', []):
                            video_id = item['contentDetails']['videoId']
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            videos.append(video_url)
                            
                            if len(videos) >= max_videos:
                                break
                        
                        # Check if there are more pages
                        next_page_token = response.get('nextPageToken')
                        if not next_page_token:
                            break
                    
                    if videos:
                        logger.info(f"Found {len(videos)} videos in playlist using YouTube API")
                        return videos
                except Exception as e:
                    logger.warning(f"YouTube API error for playlist: {e}")
            
            # Fallback to yt-dlp if YouTube API failed or not available
            logger.warning("YouTube API not available, falling back to yt-dlp for playlist")
            
            # Check if it's a URL or an ID
            if not playlist_id_or_url.startswith('http'):
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id_or_url}"
            else:
                playlist_url = playlist_id_or_url
            
            # Configure yt-dlp
            ydl_opts = {
                'extract_flat': True,
                'quiet': True,
                'playlistend': max_videos
            }
            
            # Extract playlist info
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_dict = ydl.extract_info(playlist_url, download=False)
                
                if not playlist_dict:
                    logger.warning(f"Could not extract playlist info: {playlist_url}")
                    return []
                
                # Extract video URLs
                videos = []
                for video in playlist_dict.get('entries', []):
                    if video:
                        video_url = f"https://www.youtube.com/watch?v={video['id']}"
                        videos.append(video_url)
                
                return videos
        except Exception as e:
            logger.error(f"Error fetching playlist: {e}")
            return []
    
    def analyze_with_gemini(self, text, podcast_name, episode_title):
        """
        Analyze text with Gemini to extract stock mentions and summarize
        
        :param text: Text to analyze
        :param podcast_name: Podcast name
        :param episode_title: Episode title
        :return: Analysis result or None if quality is insufficient
        """
        max_retries = 3
        retry_delay = 10  # sekunder mellan försök

        for attempt in range(max_retries):
            try:
                # Behåll befintlig kod för API-nyckel och import
                api_key = self.google_api_key or os.getenv('GOOGLE_API_KEY')
                
                if not api_key:
                    return {
                        "summary": "Gemini API not configured",
                        "mentions": []
                    }
                
                try:
                    import google.generativeai as genai
                    
                    # Befintlig konfiguration
                    genai.configure(api_key=api_key)
                    
                    # Befintlig längdbegränsning
                    if len(text) > 90000:
                        logger.info(f"Text is very long ({len(text)} characters), limiting to 90,000 characters")
                        text = text[:90000]
                
                    prompt = f"""
                    Podcast Analysis: "{podcast_name}" - Episode: "{episode_title}"

                    Analysera denna svenskspråkiga podcast-transkription med fokus på den svenska och nordiska finansmarknaden:

                    1. Skriv en koncis sammanfattning på svenska (3-5 meningar) som fångar huvudämnena i podcasten
                    2. Identifiera alla omnämnanden av:
                    - Svenska börshörnbolag (från Stockholmsbörsen, First North, NGM)
                    - Nordiska börsnoterade bolag
                    - Globala aktier som diskuteras i en svensk kontext
                    - Finansiella instrument och investeringsprodukter (fonder, ETF:er, certifikat, etc.)

                    För varje omnämnande, samla in följande information:
                    - Företagets/aktiens namn
                    - Tickersymbol exakt som den nämns (t.ex. ERIC B, SHB A) eller null om den inte nämns
                    - Ett direkt citat som visar kontexten (högst 150 tecken)
                    - Sentiment (positive/negative/neutral) baserat på hur aktien diskuteras
                    - Rekommendation (buy/sell/hold/none) om sådan nämns eller antyds tydligt
                    - Prisinformation eller prognos om sådan nämns (exakta siffror om möjligt)
                    - En kort beskrivning av varför aktien nämns (t.ex. "kvartalsrapport", "produktlansering", "populär aktie")

                    Returnera resultatet som JSON med följande struktur:
                    {{
                        "summary": "En sammanfattande text på svenska om podcasten",
                        "mentions": [
                            {{
                                "name": "Företagsnamn",
                                "ticker": "Tickersymbol eller null",
                                "context": "Citat från texten",
                                "sentiment": "positive/negative/neutral",
                                "recommendation": "buy/sell/hold/none",
                                "price_info": "Prisinformation eller null",
                                "mention_reason": "Orsak till omnämnande"
                            }}
                        ]
                    }}

                    VIKTIGT: 
                    - Inkludera INTE några kommentarer, förklaringar eller anteckningar i JSON-svaret
                    - JSON måste vara helt giltig utan några kommentarer eller förklaringar
                    - Använd "null" för värden som saknas, inte tomma strängar
                    - Var så exakt och specifik som möjligt med tickersymboler (inkludera A/B/C-suffixet för svenska aktier)
                    - För sentiment, använd endast värdena "positive", "negative" eller "neutral"
                    - För recommendation, använd endast värdena "buy", "sell", "hold" eller "none"

                    Text att analysera:
                    {text}
                    """
                
                    # Befintlig modellinstans och innehållsgenerering
                    model = genai.GenerativeModel("gemini-1.5-pro")
                    response = model.generate_content(prompt)
                    
                    # Befintlig JSON-rensning
                    response_text = response.text
                    if response_text.startswith("```json") or response_text.startswith("```"):
                        response_text = response_text.replace("```json", "").replace("```", "").strip()
                    
                    # Modifierad JSON-parsing och kvalitetskontroll
                    try:
                        result = json.loads(response_text)
                        logger.info(f"Gemini analysis completed with API key, found {len(result.get('mentions', []))} mentions")
                        
                        mentions = result.get('mentions', [])
                        summary = result.get('summary', '')
                        
                        # Ändrad kvalitetskontroll - mindre strikta krav
                        if len(mentions) >= 1 and len(summary) > 50:
                            return result
                        
                        logger.warning(f"Analysis quality too low: {len(mentions)} mentions, summary length: {len(summary)}")
                        
                        # Vänta innan nästa försök
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponentiell backoff
                        
                        continue  # Fortsätt till nästa iteration
                    
                    except json.JSONDecodeError as e:
                        logger.error(f"Could not parse Gemini response as JSON: {e}")
                        logger.error(f"Response text: {response_text}")
                        
                        # Vänta innan nästa försök
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponentiell backoff
                        
                        continue  # Fortsätt till nästa iteration
                    
                except Exception as e:
                    logger.error(f"Error using Gemini with API key: {e}")
                    
                    # Specifik hantering för 429-fel (kvotfel)
                    if "429" in str(e):
                        logger.warning("API-kvotfel. Väntar mellan försök...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponentiell backoff
                        continue
                    
                    # För andra fel, returnera ett standardsvar
                    return {
                        "summary": "Error analyzing with Gemini",
                        "mentions": []
                    }
            
            except Exception as e:
                logger.error(f"Generellt fel vid Gemini-analys: {e}")
                
                # Vänta innan nästa försök
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponentiell backoff
        
        # Om alla försök misslyckas
        logger.error("Kunde inte genomföra Gemini-analys efter flera försök")
        return {
            "summary": "Analys kunde inte genomföras efter flera försök",
            "mentions": []
        }
    
    def save_analysis(self, podcast_name, items):
        """
        Save analysis results to a JSON file with improved naming convention
        Each episode is saved in a separate file
        
        :param podcast_name: Podcast name
        :param items: List of analyzed items
        :return: List of paths to saved files
        """
        saved_files = []
        
        # Spara varje episod i en separat fil
        for item in items:
            # Extrahera avsnittsnummer från titeln om möjligt
            title = item.get('title', '')
            episode_number = None
            # Mönster för att hitta avsnittsnummer som "Sparpodden 555" eller "Avsnitt 123" eller "#382"
            match = re.search(r'(?:[Ss]parpodden|[Aa]vsnitt|[Ee]pisode|#)\s*#?(\d+)', title)
            if match:
                episode_number = match.group(1)
            
            # Extrahera publiceringsdatum
            pub_date = item.get('published_at', '')
            # Konvertera från ISO-format till YYYYMMDD
            if pub_date and pub_date != 'Unknown':
                try:
                    # Hantera ISO 8601-format "2023-01-15T12:30:45Z"
                    pub_date = pub_date.split('T')[0].replace('-', '')
                except Exception:
                    pub_date = ''
            
            # Skapa filnamn med avsnittsnummer och publiceringsdatum om tillgängliga
            filename_parts = [podcast_name.replace(' ', '_').lower()]
            
            if episode_number:
                filename_parts.append(f"ep{episode_number}")
            
            if pub_date:
                filename_parts.append(f"pub{pub_date}")
            
            # Lägg till en tidsstämpel för när analysen gjordes
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_parts.append(timestamp)
            
            filename = os.path.join(
                self.data_dir, 
                f"{'_'.join(filename_parts)}.json"
            )
            
            # Spara enstaka episod i egen fil
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "podcast_name": podcast_name,
                    "analysis_date": datetime.now().isoformat(),
                    "items": [item]  # OBS: Bara en episod i listan nu
                }, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Saved analysis for {podcast_name} - {title} to {filename}")
            saved_files.append(filename)
        
        return saved_files
    
    def save_to_database(self, podcast_name, items):
        """
        Save analysis results to the database with improved error handling
        
        :param podcast_name: Podcast name
        :param items: List of analyzed items
        :return: Boolean indicating success
        """
        if not self.db_session:
            logger.warning("Database session not available, skipping database save")
            return False
        
        try:
            from models import Podcast, Episode, StockMention
            from datetime import datetime
            
            # Reducera kravet på antal omnämnanden
            valid_items = [
                item for item in items 
                if len(item.get('mentions', [])) >= 1
            ]
            
            if not valid_items:
                logger.warning("No valid items to save to database")
                return False
            
            # Skapa en ny session
            session = self.db_session()
            
            try:
                # Transaktionshantering
                with session.begin():
                    # Hämta eller skapa podcast
                    podcast = session.query(Podcast).filter_by(name=podcast_name).first()
                    if not podcast:
                        podcast = Podcast(
                            name=podcast_name,
                            playlist_id=self.podcasts.get(podcast_name)
                        )
                        session.add(podcast)
                    
                    # Bearbeta varje analyserad artikel
                    for item in valid_items:
                        # Undvik dubbletter
                        existing_episode = (
                            session.query(Episode)
                            .filter_by(video_id=item['video_id'])
                            .first()
                        )
                        
                        if existing_episode:
                            logger.info(f"Episode {item['video_id']} already exists, skipping")
                            continue
                        
                        # Hantera publiceringsdatum
                        published_at = None
                        if item.get('published_at') and item['published_at'] != 'Unknown':
                            try:
                                published_at = datetime.strptime(
                                    item['published_at'].split('T')[0], 
                                    '%Y-%m-%d'
                                )
                            except Exception as e:
                                logger.warning(f"Kunde inte tolka publiceringsdatum: {e}")
                        
                        # Skapa ny episod
                        episode = Episode(
                            video_id=item['video_id'],
                            title=item.get('title', 'Okänd titel')[:255],
                            video_url=item.get('video_url', '')[:512],
                            published_at=published_at,
                            description=item.get('description', '')[:1000],
                            summary=item.get('summary', '')[:2000],
                            transcript_length=item.get('transcript_length', 0),
                            analysis_date=datetime.now(),
                            podcast=podcast
                        )
                        session.add(episode)
                        
                        # Lägg till aktieomtal
                        for mention in item.get('mentions', []):
                            # Lägg till denna förbättring för alla fält som kan vara None
                            stock_mention = StockMention(
                                name=mention.get('name', 'Okänt')[:255],
                                ticker=(mention.get('ticker') or '')[:50],
                                context=(mention.get('context', ''))[:500],
                                sentiment=(mention.get('sentiment', 'neutral'))[:50],
                                recommendation=(mention.get('recommendation', 'none'))[:50],
                                price_info=(mention.get('price_info') or '')[:255],
                                mention_reason=(mention.get('mention_reason') or '')[:255],
                                episode=episode
                            )
                            session.add(stock_mention)
                
                # Commit och stäng sessionen
                session.commit()
                logger.info(f"Sparade {len(valid_items)} episoder till databasen")
                return True
            
            except Exception as e:
                session.rollback()
                logger.error(f"Databaslagringsfel: {e}")
                return False
            finally:
                # Stäng sessionen
                session.close()
        
        except Exception as e:
            logger.error(f"Generellt databasfel: {e}")
            return False
    
    def analyze_youtube_urls(self, urls, podcast_name="YouTube Podcast"):
        """
        Analyze a list of individual YouTube URLs
        
        :param urls: List of YouTube video URLs
        :param podcast_name: Name of the podcast
        :return: List of analyzed items
        """
        analyzed_items = []
        
        for i, url in enumerate(urls):
            print(f"\n{Fore.CYAN}===== Analyserar Video {i+1}/{len(urls)} ====={Style.RESET_ALL}")
            print(f"URL: {url}")
            
            # Get video info
            video_info = self.get_video_info(url)
            video_id = video_info.get('video_id')
            
            # Kontrollera om videon redan har analyserats
            if video_id != 'Unknown' and self.has_analyzed_video(video_id):
                print(f"{Fore.YELLOW}Video {video_id} already analyzed, skipping{Style.RESET_ALL}")
                continue
            
            # Get transcript from YouTubeToTranscript.com
            transcript_text = self.get_transcript_from_website(url)
            
            if transcript_text:
                print(f"{Fore.GREEN}Transcript fetched successfully ({len(transcript_text)} characters){Style.RESET_ALL}")
                
                # Analyze transcript with Gemini
                if self.google_api_key:  # ändrat från google_cloud_project
                    print(f"{Fore.CYAN}Analyzing transcript with Gemini...{Style.RESET_ALL}")
                    analysis = self.analyze_with_gemini(
                        transcript_text, 
                        podcast_name, 
                        video_info['title']
                    )
                else:
                    # If Gemini is not configured, just return basic info
                    analysis = {
                        "summary": "Gemini analysis not configured",
                        "mentions": []
                    }
                
                # Combine analysis with item metadata
                full_item = {
                    **video_info,
                    **analysis,
                    'transcript_length': len(transcript_text)
                }
                
                analyzed_items.append(full_item)
            else:
                # Om ingen transkribering hittas, analysera beskrivningen istället
                print(f"{Fore.RED}Could not fetch transcript{Style.RESET_ALL}")
                
                if video_info['description'] and len(video_info['description']) > 100:
                    print(f"{Fore.YELLOW}Analyzing description instead{Style.RESET_ALL}")
                    
                    if self.google_api_key:  # ändrat från google_cloud_project
                        analysis = self.analyze_with_gemini(
                            video_info['description'],
                            podcast_name,
                            video_info['title']
                        )
                    else:
                        analysis = {
                            "summary": "Gemini analysis not configured",
                            "mentions": []
                        }
                    
                    # Combine analysis with item metadata
                    full_item = {
                        **video_info,
                        **analysis,
                        'using_description': True
                    }
                    
                    analyzed_items.append(full_item)
                else:
                    print(f"{Fore.RED}No transcript or useful description available{Style.RESET_ALL}")
            
            # Add a delay to avoid overwhelming the website
            if i < len(urls) - 1:
                print(f"{Fore.CYAN}Waiting before processing next video...{Style.RESET_ALL}")
                time.sleep(3)
        
        # Save analysis results if we have any
        if analyzed_items:
            saved_files = self.save_analysis(podcast_name, analyzed_items)
            for file in saved_files:
                print(f"{Fore.GREEN}Analysis saved to: {file}{Style.RESET_ALL}")
        
            # Also save to database if available
            if self.db_session:
                if self.save_to_database(podcast_name, analyzed_items):
                    print(f"{Fore.GREEN}Data also saved to database{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}Failed to save to database{Style.RESET_ALL}")
        
        return analyzed_items
    
    def analyze_podcast_playlist(self, podcast_name, playlist_id, max_episodes=5):
        """
        Analyze a complete podcast playlist
        
        :param podcast_name: Podcast name
        :param playlist_id: YouTube playlist ID
        :param max_episodes: Maximum number of episodes to analyze
        """
        print(f"\n{Fore.CYAN}Analyzing playlist: {podcast_name}{Style.RESET_ALL}")
        
        # Get videos from playlist
        video_urls = self.get_playlist_videos(playlist_id, max_videos=max_episodes)
        
        if not video_urls:
            print(f"{Fore.RED}No videos found in playlist. Using fallback list.{Style.RESET_ALL}")
            
            # Empty fallback - will try to get videos from playlist first
            fallback = {}
            
            # Try to get fallback videos for this podcast
            if podcast_name in fallback:
                video_urls = fallback[podcast_name][:max_episodes]
            
            if not video_urls:
                print(f"{Fore.RED}No fallback videos available for this podcast{Style.RESET_ALL}")
                return []
        
        print(f"{Fore.GREEN}Found {len(video_urls)} videos to analyze{Style.RESET_ALL}")
        
        # Analyze each video
        return self.analyze_youtube_urls(video_urls, podcast_name)

    def import_transcript_from_file(self, file_path, video_url=None, podcast_name="Imported Podcast"):
        """
        Import and analyze a transcript from a local file
        
        :param file_path: Path to transcript file
        :param video_url: Associated YouTube URL (optional)
        :param podcast_name: Name of the podcast
        :return: Analysis result
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read()
            
            print(f"{Fore.GREEN}Loaded transcript from file: {file_path} ({len(transcript_text)} characters){Style.RESET_ALL}")
            
            # Extract file name as title if no video URL provided
            title = os.path.basename(file_path)
            if title.endswith('.txt'):
                title = title[:-4]  # Remove .txt extension
            
            # Get video info if URL provided
            video_info = {
                'title': title,
                'video_id': 'local_' + title.replace(' ', '_'),
                'video_url': video_url or 'local_file',
                'published_at': datetime.now().strftime('%Y-%m-%d'),
                'description': f"Imported from {file_path}"
            }
            
            if video_url:
                try:
                    video_info = self.get_video_info(video_url)
                except Exception as e:
                    logger.warning(f"Could not get video info for {video_url}: {e}")
            
            # Analyze transcript
            if self.google_api_key:  # ändrat från google_cloud_project
                analysis = self.analyze_with_gemini(
                    transcript_text,
                    podcast_name,
                    video_info['title']
                )
            else:
                analysis = {
                    "summary": "Gemini analysis not configured",
                    "mentions": []
                }
            
            # Combine analysis with item metadata
            full_item = {
                **video_info,
                **analysis,
                'transcript_length': len(transcript_text),
                'imported_from': file_path
            }
            
            # Save analysis
            analyzed_items = [full_item]
            saved_file = self.save_analysis(podcast_name, analyzed_items)
            print(f"{Fore.GREEN}Analysis saved to: {saved_file}{Style.RESET_ALL}")
            
            return full_item
        
        except Exception as e:
            logger.error(f"Error importing transcript from file: {e}")
            return None


def export_to_csv(results, output_file):
    """
    Export analysis results to CSV file
    
    :param results: List of analysis results
    :param output_file: Path to output CSV file
    """
    try:
        # Flatten mentions for CSV export
        export_data = []
        for result in results:
            podcast_name = result.get('podcast_name', 'Unknown')
            for mention in result.get('mentions', []):
                export_item = {
                    'Podcast': podcast_name,
                    'Episode': result.get('title', 'Unknown'),
                    'Date': result.get('published_at', 'Unknown'),
                    'Stock': mention['name'],
                    'Ticker': mention.get('ticker', ''),
                    'Sentiment': mention.get('sentiment', 'unknown'),
                    'Recommendation': mention.get('recommendation', 'None'),
                    'PriceInfo': mention.get('price_info', ''),
                    'Context': mention.get('context', '')
                }
                export_data.append(export_item)
        
        # Export to CSV
        df = pd.DataFrame(export_data)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"{Fore.GREEN}Results exported to {output_file}{Style.RESET_ALL}")
        
    except Exception as e:
        logger.error(f"Error exporting results to CSV: {e}")
        print(f"{Fore.RED}Error exporting results: {e}{Style.RESET_ALL}")

def print_analysis_summary(results, filter_stock=None):
    """
    Print a summary of the analysis results
    
    :param results: List of analysis results
    :param filter_stock: Optional stock name to filter mentions
    """
    if not results:
        print(f"{Fore.YELLOW}No results to display{Style.RESET_ALL}")
        return
    
    # Print summary for each analyzed item
    all_mentions = []
    for item in results:
        mentions = item.get('mentions', [])
        all_mentions.extend(mentions)
        
        if mentions:
            print(f"\n{Fore.YELLOW}{item['title']}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Summary: {item.get('summary', 'No summary available')}{Style.RESET_ALL}")
            
            for mention in mentions:
                # Filter by stock name if requested
                if filter_stock and filter_stock.lower() not in mention['name'].lower():
                    continue
                    
                ticker_info = f" ({mention.get('ticker')})" if mention.get('ticker') else ""
                sentiment_color = Fore.GREEN if mention.get('sentiment') == 'positive' else Fore.RED if mention.get('sentiment') == 'negative' else Fore.YELLOW
                print(f"  - {mention['name']}{ticker_info} ({sentiment_color}{mention.get('sentiment', 'unknown')}{Style.RESET_ALL})")
                if mention.get('recommendation') and mention['recommendation'] != 'none':
                    print(f"    Recommendation: {Fore.CYAN}{mention['recommendation']}{Style.RESET_ALL}")
                if mention.get('price_info'):
                    print(f"    Price Info: {mention['price_info']}")
                if mention.get('context'):
                    print(f"    Context: \"{mention['context']}\"")
    
    # Print summary stats
    print(f"\n{Fore.GREEN}Total episodes analyzed: {len(results)}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Total stock mentions: {len(all_mentions)}{Style.RESET_ALL}")

def main():
    # Load environment variables
    load_dotenv()
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='YouTube Podcast Stock Mention Analyzer')
    parser.add_argument('url', nargs='?', 
                    help='YouTube URL (video or playlist)')
    parser.add_argument('--podcast', '-p', 
                    help='Podcast name for the analysis')
    parser.add_argument('--podcasts', nargs='+', 
                    help='Specific podcasts to analyze from predefined list')
    parser.add_argument('--episodes', '-e', type=int, default=5, 
                    help='Number of episodes to analyze per podcast')
    parser.add_argument('--export', '-x', 
                    help='Export results to a specific CSV file')
    parser.add_argument('--stock', '-s', 
                    help='Search for mentions of a specific stock')
    parser.add_argument('--transcripts-only', action='store_true',
                    help='Only fetch transcripts without analysis')
    parser.add_argument('--import-transcript', '-i',
                    help='Import transcript from a local file')
    parser.add_argument('--output-dir', '-o', default='podcast_data',
                    help='Directory to save output files')
    parser.add_argument('--list-podcasts', action='store_true',
                    help='List all available predefined podcasts')
    parser.add_argument('--db-host', 
                    help='Database host')
    parser.add_argument('--db-port', type=int, default=5432,
                    help='Database port')
    parser.add_argument('--db-name', default='postgres',
                    help='Database name')
    parser.add_argument('--db-user', default='postgres',
                    help='Database username')
    parser.add_argument('--db-password',
                    help='Database password')
    parser.add_argument('--use-db', action='store_true',
                    help='Use database connection from .env if available')
    args = parser.parse_args()
    
    # Get API keys from environment
    youtube_api_key = os.getenv('YOUTUBE_API_KEY')
    google_api_key = os.getenv('GOOGLE_API_KEY') 
    
    # Configure database connection
    db_url = None

    # First check command line arguments
    if args.db_host and args.db_password:
        db_url = f"postgresql://{args.db_user}:{args.db_password}@{args.db_host}:{args.db_port}/{args.db_name}"
        print(f"{Fore.CYAN}Using database connection from command line arguments{Style.RESET_ALL}")
    # Then check environment variables if --use-db flag is present
    elif args.use_db:
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'postgres')
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD')
        
        if db_host and db_password:
            db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            print(f"{Fore.CYAN}Using database connection from environment variables{Style.RESET_ALL}")
    
    # Lägg till denna kod precis innan raden med analyzer-initieringen
    if db_url:
        try:
            import sqlalchemy
            engine = sqlalchemy.create_engine(db_url)
            with engine.connect() as connection:
                print(f"{Fore.GREEN}Databasanslutning lyckades!{Style.RESET_ALL}")
                # Du kan köra en enkel testfråga här om du vill
                result = connection.execute(sqlalchemy.text("SELECT version()"))
                print(f"Databasversion: {result.fetchone()[0]}")
        except Exception as e:
            print(f"{Fore.RED}Kunde inte ansluta till databasen: {e}{Style.RESET_ALL}")
    # Initialize analyzer with available credentials
    analyzer = YouTubePodcastAnalyzer(youtube_api_key, google_api_key, args.output_dir, db_url)
    
    # List available podcasts if requested
    if args.list_podcasts:
        print(f"{Fore.CYAN}Available podcasts:{Style.RESET_ALL}")
        for idx, name in enumerate(analyzer.podcasts.keys(), 1):
            print(f"{idx}. {name}")
        return
    
    # Collect all results for potential export
    all_results = []
    
    # Import transcript from file if requested
    if args.import_transcript:
        if not os.path.exists(args.import_transcript):
            print(f"{Fore.RED}Transcript file not found: {args.import_transcript}{Style.RESET_ALL}")
            return
        
        podcast_name = args.podcast or "Imported Podcast"
        result = analyzer.import_transcript_from_file(
            args.import_transcript,
            args.url,
            podcast_name
        )
        
        if result:
            all_results.append(result)
            print_analysis_summary([result], args.stock)
        
        # Export if requested
        if args.export and all_results:
            export_to_csv(all_results, args.export)
        
        return
    
    # Process single URL if provided
    if args.url:
        podcast_name = args.podcast or "YouTube Video"
        
        # Check if it's a playlist
        if "playlist" in args.url or "list=" in args.url:
            print(f"{Fore.CYAN}Processing playlist: {args.url}{Style.RESET_ALL}")
            results = analyzer.analyze_podcast_playlist(
                podcast_name,
                args.url,
                max_episodes=args.episodes
            )
        else:
            # Single video
            print(f"{Fore.CYAN}Processing single video: {args.url}{Style.RESET_ALL}")
            results = analyzer.analyze_youtube_urls([args.url], podcast_name)
        
        all_results.extend(results)
    
    # Process predefined podcasts if requested
    elif args.podcasts:
        for podcast_name in args.podcasts:
            playlist_id = analyzer.podcasts.get(podcast_name)
            
            if not playlist_id:
                print(f"{Fore.YELLOW}No playlist found for {podcast_name}{Style.RESET_ALL}")
                continue
            
            results = analyzer.analyze_podcast_playlist(
                podcast_name, 
                playlist_id, 
                max_episodes=args.episodes
            )
            
            all_results.extend(results)
    else:
        if not args.import_transcript:
            print(f"{Fore.YELLOW}No podcast or URL specified. Use --podcasts or provide a URL.{Style.RESET_ALL}")
            parser.print_help()
            return
    
    # Print analysis summary
    if all_results:
        print_analysis_summary(all_results, args.stock)
        
        # Export results if requested
        if args.export:
            export_to_csv(all_results, args.export)
    else:
        print(f"{Fore.YELLOW}No results were generated. Check your inputs and try again.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()