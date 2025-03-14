from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os
import logging
import traceback
from datetime import datetime
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("podcast_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("podcast-scraper")

class PodcastScraper:
    def __init__(self, spotify_username, spotify_password):
        """Initialize the podcast scraper with Spotify credentials."""
        self.spotify_username = spotify_username
        self.spotify_password = spotify_password
        self.results_dir = "podcast_data"
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Create results directory if it doesn't exist
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
            
        # Path to the results file
        self.results_file = os.path.join(self.results_dir, "podcast_stock_analysis.json")
        
        logger.info("PodcastScraper initialized")

    def setup_driver(self):
        """Configure and return a Chrome webdriver instance."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Use ChromeDriverManager to automatically download the correct driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set page load timeout
            driver.set_page_load_timeout(30)
            
            logger.info("Chrome WebDriver setup completed")
            return driver
        except Exception as e:
            logger.error(f"Error setting up Chrome WebDriver: {e}")
            logger.error(traceback.format_exc())
            raise

    def login_to_spotify(self, driver):
        """Log in to Spotify Web Player using provided credentials."""
        try:
            logger.info("Navigating to Spotify login page")
            driver.get("https://open.spotify.com/")
            time.sleep(2)
            
            # Click on login button
            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='login-button']"))
            )
            login_button.click()
            logger.info("Clicked login button")
            
            # Fill in username and password
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "login-username"))
            )
            username_field = driver.find_element(By.ID, "login-username")
            password_field = driver.find_element(By.ID, "login-password")
            
            username_field.send_keys(self.spotify_username)
            password_field.send_keys(self.spotify_password)
            logger.info("Entered login credentials")
            
            # Click login submit button
            login_submit = driver.find_element(By.ID, "login-button")
            login_submit.click()
            logger.info("Submitted login form")
            
            # Wait for login to complete
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='user-widget-link']"))
            )
            
            logger.info("Successfully logged in to Spotify")
            return True
        except Exception as e:
            logger.error(f"Login to Spotify failed: {e}")
            logger.error(traceback.format_exc())
            return False

    def navigate_to_podcast(self, driver, podcast_name):
        """Search for and navigate to a specific podcast."""
        try:
            logger.info(f"Navigating to podcast: {podcast_name}")
            
            # Click on search icon
            search_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='search-icon']"))
            )
            search_button.click()
            logger.info("Clicked search icon")
            
            # Enter podcast name in search field
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='search-input']"))
            )
            search_input.clear()
            search_input.send_keys(podcast_name)
            logger.info(f"Entered '{podcast_name}' in search field")
            time.sleep(2)  # Wait for search results
            
            # Look for podcast results
            # Try finding podcast cards with different selectors
            podcast_selectors = [
                "[data-testid='podcast-card']",
                "[data-testid='show-card']", 
                "a[href*='show']"
            ]
            
            podcast_result = None
            for selector in podcast_selectors:
                try:
                    podcast_result = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    if podcast_result:
                        break
                except:
                    continue
            
            if not podcast_result:
                logger.error(f"Could not find podcast: {podcast_name}")
                return False
                
            podcast_result.click()
            logger.info(f"Clicked on podcast result for {podcast_name}")
            
            # Wait for podcast page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section[data-testid='show-page']"))
            )
            
            logger.info(f"Successfully navigated to podcast: {podcast_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to podcast '{podcast_name}': {e}")
            logger.error(traceback.format_exc())
            return False

    def get_podcast_episodes(self, driver, max_episodes=5):
        """Extract information about podcast episodes."""
        episodes = []
        try:
            logger.info(f"Extracting up to {max_episodes} podcast episodes")
            
            # Wait for the episode list to load
            episode_items = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='episode-item']"))
            )
            
            # Limit to max_episodes
            episode_items = episode_items[:min(max_episodes, len(episode_items))]
            
            for index, episode in enumerate(episode_items):
                try:
                    # Extract title
                    title_element = episode.find_element(By.CSS_SELECTOR, "[data-testid='episodeTitle']")
                    title = title_element.text
                    
                    # Extract date
                    date_element = episode.find_element(By.CSS_SELECTOR, "[data-testid='episodeDate']")
                    date = date_element.text
                    
                    # Extract link
                    link_element = episode.find_element(By.CSS_SELECTOR, "a")
                    link = link_element.get_attribute("href")
                    
                    # Extract description (optional)
                    description = ""
                    try:
                        description_element = episode.find_element(By.CSS_SELECTOR, "[data-testid='episodeDescription']")
                        description = description_element.text
                    except:
                        pass
                    
                    episodes.append({
                        "title": title,
                        "date": date,
                        "link": link,
                        "description": description
                    })
                    logger.info(f"Extracted episode {index+1}/{len(episode_items)}: {title}")
                    
                except Exception as e:
                    logger.error(f"Failed to extract episode data: {e}")
                    continue
                    
            logger.info(f"Successfully extracted {len(episodes)} episodes")
            return episodes
        except Exception as e:
            logger.error(f"Failed to extract episode list: {e}")
            logger.error(traceback.format_exc())
            return []

    def extract_episode_transcript(self, driver, episode_link):
        """Attempt to extract transcript for an episode if available."""
        try:
            logger.info(f"Navigating to episode: {episode_link}")
            driver.get(episode_link)
            time.sleep(3)
            
            # Check if there's a "Show transcript" button
            transcript_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Show transcript') or contains(text(), 'Visa transkript')]")
            
            if not transcript_buttons:
                logger.info("No transcript available for this episode")
                return None
                
            # Click the button to show transcript
            transcript_buttons[0].click()
            logger.info("Clicked 'Show transcript' button")
            time.sleep(2)
            
            # Extract transcript segments
            transcript_segments = driver.find_elements(By.CSS_SELECTOR, "[data-testid='transcriptSegment']")
            
            if not transcript_segments:
                # Try alternate selectors
                selectors_to_try = [
                    ".R4AOm8lBixAuXc0WRiMc",  # Common transcript segment class
                    ".transcript-segment",
                    "[role='listitem']"
                ]
                
                for selector in selectors_to_try:
                    transcript_segments = driver.find_elements(By.CSS_SELECTOR, selector)
                    if transcript_segments:
                        break
            
            if not transcript_segments:
                logger.info("Could not find transcript segments")
                return None
                
            transcript_text = ""
            for segment in transcript_segments:
                transcript_text += segment.text + " "
                
            logger.info(f"Successfully extracted transcript ({len(transcript_text)} characters)")
            return transcript_text.strip()
            
        except Exception as e:
            logger.error(f"Failed to extract transcript: {e}")
            logger.error(traceback.format_exc())
            return None

    def analyze_transcript_for_stocks(self, transcript, episode_info):
        """Analyze transcript for stock mentions using OpenAI API."""
        if not transcript:
            logger.info("No transcript available for analysis")
            return {"error": "No transcript available for analysis"}
        
        try:
            logger.info("Analyzing transcript for stock mentions")
            
            # Prepare transcript for analysis (limit to manageable size)
            transcript_text = transcript[:15000]  # Limit to first 15000 chars
            
            prompt = f"""
            Analyze the following podcast transcript from the episode "{episode_info['title']}" for any mentions of stocks, 
            companies, or financial instruments. For each mention, identify:
            
            1. The name of the company/stock
            2. The context in which it was mentioned (short excerpt)
            3. The sentiment (positive, negative, or neutral)
            4. Any price indicators or predictions mentioned (if any)
            
            Format the response as a JSON object with an array of mentions.
            
            Transcript:
            {transcript_text}
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial analyst expert at identifying mentions of stocks and companies in podcast transcripts."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Analysis complete, found {len(result.get('mentions', []))} stock mentions")
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze transcript: {e}")
            logger.error(traceback.format_exc())
            return {"error": f"Analysis error: {str(e)}"}

    def run(self, podcast_names, max_episodes=3):
        """Run the full podcast analysis process."""
        logger.info(f"Starting analysis for podcasts: {podcast_names}")
        
        driver = None
        all_results = []
        
        try:
            # Setup the WebDriver
            driver = self.setup_driver()
            
            # Login to Spotify
            if not self.login_to_spotify(driver):
                logger.error("Failed to log in to Spotify. Aborting analysis.")
                return
            
            # Process each podcast
            for podcast_name in podcast_names:
                logger.info(f"Processing podcast: {podcast_name}")
                
                # Navigate to podcast
                if not self.navigate_to_podcast(driver, podcast_name):
                    logger.warning(f"Skipping podcast: {podcast_name}")
                    continue
                    
                # Get episodes
                episodes = self.get_podcast_episodes(driver, max_episodes)
                
                podcast_results = {
                    "podcast_name": podcast_name,
                    "analysis_date": datetime.now().isoformat(),
                    "episodes": []
                }
                
                # Analyze each episode
                for episode in episodes:
                    logger.info(f"Analyzing episode: {episode['title']}")
                    
                    # Extract transcript
                    transcript = self.extract_episode_transcript(driver, episode['link'])
                    
                    # Analyze transcript
                    analysis = None
                    if transcript:
                        analysis = self.analyze_transcript_for_stocks(transcript, episode)
                    
                    episode_result = {
                        "title": episode['title'],
                        "date": episode['date'],
                        "link": episode['link'],
                        "has_transcript": transcript is not None,
                        "stock_analysis": analysis
                    }
                    
                    podcast_results["episodes"].append(episode_result)
                
                all_results.append(podcast_results)
            
            # Save the results
            self._save_results(all_results)
            
            logger.info("Analysis completed successfully")
            return all_results
            
        except Exception as e:
            logger.error(f"An unexpected error occurred during podcast analysis: {e}")
            logger.error(traceback.format_exc())
            return []
        finally:
            # Clean up
            if driver:
                driver.quit()
                logger.info("WebDriver closed")

    def _save_results(self, results):
        """Save analysis results to a JSON file."""
        try:
            # Read existing results if available
            existing_results = []
            if os.path.exists(self.results_file):
                with open(self.results_file, 'r', encoding='utf-8') as f:
                    existing_results = json.load(f)
            
            # Combine with new results
            # Replace existing entries with new ones
            podcast_names = [r['podcast_name'] for r in results]
            filtered_existing = [r for r in existing_results if r['podcast_name'] not in podcast_names]
            combined_results = filtered_existing + results
            
            # Save to file
            with open(self.results_file, 'w', encoding='utf-8') as f:
                json.dump(combined_results, f, ensure_ascii=False, indent=4)
                
            logger.info(f"Results saved to {self.results_file}")
            
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            logger.error(traceback.format_exc())

    def get_latest_results(self, podcast_name=None):
        """
        Get the latest analysis results.
        If podcast_name is specified, return results for that podcast only.
        """
        try:
            if not os.path.exists(self.results_file):
                logger.warning("No analysis results found")
                return [] if podcast_name is None else None
                
            with open(self.results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                
            if podcast_name:
                for podcast in results:
                    if podcast['podcast_name'].lower() == podcast_name.lower():
                        return podcast
                return None
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get latest results: {e}")
            logger.error(traceback.format_exc())
            return [] if podcast_name is None else None

    def get_stock_mentions(self, stock_name=None):
        """
        Get all stock mentions from analyzed podcasts.
        If stock_name is specified, filter for that stock only.
        """
        try:
            results = self.get_latest_results()
            if not results:
                return []
                
            all_mentions = []
            
            for podcast in results:
                podcast_name = podcast['podcast_name']
                
                for episode in podcast.get('episodes', []):
                    # Skip episodes without analysis
                    if not episode.get('stock_analysis') or not episode['stock_analysis'].get('mentions'):
                        continue
                        
                    mentions = episode['stock_analysis']['mentions']
                    
                    # Filter by stock name if specified
                    if stock_name:
                        mentions = [
                            mention for mention in mentions 
                            if stock_name.lower() in mention.get('name', '').lower()
                        ]
                    
                    if mentions:
                        all_mentions.append({
                            "podcast": podcast_name,
                            "episode": episode['title'],
                            "date": episode['date'],
                            "link": episode['link'],
                            "mentions": mentions
                        })
            
            return all_mentions
            
        except Exception as e:
            logger.error(f"Failed to get stock mentions: {e}")
            logger.error(traceback.format_exc())
            return []
