#!/usr/bin/env python3
import os
import sys
import argparse
import logging
import json
from podcast_api import PodcastAPI
from dotenv import load_dotenv
from datetime import datetime, timedelta
import textwrap
import colorama
from colorama import Fore, Style, Back
from tabulate import tabulate

# Initiera färgutskrift
colorama.init()

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_podcast.log')
    ]
)

logger = logging.getLogger('batch_podcast')

def format_timestamp():
    """Returnera en formaterad tidsstämpel för utskrift"""
    return f"{Fore.CYAN}[{datetime.now().strftime('%H:%M:%S')}]{Style.RESET_ALL}"

def print_header(text):
    """Skriv ut en formaterad rubrik"""
    width = min(80, os.get_terminal_size().columns)
    print("\n" + "=" * width)
    print(f"{Fore.YELLOW}{Style.BRIGHT}{text.center(width)}{Style.RESET_ALL}")
    print("=" * width)

def print_subheader(text):
    """Skriv ut en formaterad underrubrik"""
    width = min(80, os.get_terminal_size().columns)
    print("\n" + "-" * width)
    print(f"{Fore.GREEN}{text}{Style.RESET_ALL}")
    print("-" * width)

def wrap_text(text, width=70):
    """Radbryter text till given bredd"""
    if not text:
        return ""
    return "\n".join(textwrap.wrap(text, width=width))

def print_episode_summary(episode, mention_count):
    """Skriv ut en sammanfattning av ett avsnitt"""
    date = episode.get('date', 'Okänt datum')
    title = episode.get('title', 'Okänd titel')
    
    color = Fore.GREEN if mention_count > 0 else Fore.WHITE
    
    print(f"\n{color}{Style.BRIGHT}{title}{Style.RESET_ALL} ({date})")
    print(f"  Länk: {Fore.BLUE}{episode.get('link', '')}{Style.RESET_ALL}")
    
    if 'has_transcript' in episode:
        transcript_status = f"{Fore.GREEN}Ja{Style.RESET_ALL}" if episode['has_transcript'] else f"{Fore.RED}Nej{Style.RESET_ALL}"
        print(f"  Transkript: {transcript_status}")
    
    print(f"  Aktieomtal: {mention_count}")
    
    # Skriv ut sammanfattning om det finns
    if episode.get('stock_analysis', {}).get('summary'):
        summary = episode['stock_analysis']['summary']
        print(f"\n  {Fore.CYAN}Sammanfattning:{Style.RESET_ALL}")
        print(f"  {wrap_text(summary)}")

def print_mention(mention, index=1):
    """Skriv ut ett aktieomtal med färg baserat på sentiment"""
    name = mention.get('name', 'Okänt företag')
    context = mention.get('context', 'Ingen kontext')
    sentiment = mention.get('sentiment', 'okänd')
    price_info = mention.get('price_info')
    
    # Välj färg baserat på sentiment
    color = Fore.GREEN if sentiment == 'positivt' else Fore.RED if sentiment == 'negativt' else Fore.YELLOW
    
    # Sentiment-emoji
    emoji = "😀" if sentiment == "positivt" else "😟" if sentiment == "negativt" else "😐"
    
    # Visa aktieomtal
    print(f"  {Style.BRIGHT}{index}. {color}{name}{Style.RESET_ALL} {emoji}")
    print(f"     {wrap_text(context)}")
    
    if price_info:
        print(f"     {Fore.CYAN}Prisinformation: {price_info}{Style.RESET_ALL}")

def print_json_pretty(data):
    """Skriv ut JSON-data formaterad och färglagd"""
    formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
    
    # Enkel färgläggning av JSON
    lines = formatted_json.splitlines()
    
    for line in lines:
        # Färglägg nycklar
        if ": " in line and not line.strip().startswith('"'):
            key_part = line.split(": ")[0]
            rest = line[len(key_part) + 2:]
            print(f"{Fore.CYAN}{key_part}{Style.RESET_ALL}: {rest}")
        # Färglägg strängar som innehåller aktienamn
        elif "name" in line or "title" in line or "summary" in line:
            print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
        # Färglägg positiva/negativa sentiment
        elif "positivt" in line:
            print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
        elif "negativt" in line:
            print(f"{Fore.RED}{line}{Style.RESET_ALL}")
        else:
            print(line)

def print_weekly_report(new_episodes, podcast_api):
    """Skriv ut veckorapport över nya avsnitt och aktieomtal"""
    print_header("VECKORAPPORT: NYA AVSNITT & AKTIEOMTAL")
    
    if not new_episodes:
        print(f"\n{Fore.YELLOW}Inga nya avsnitt hittades denna vecka.{Style.RESET_ALL}")
        return
    
    # Visa sammanfattning
    total_podcasts = len(new_episodes)
    total_episodes = sum(len(episodes) for episodes in new_episodes.values())
    
    print(f"\n{Fore.CYAN}Perioden {(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')} till {datetime.now().strftime('%Y-%m-%d')}{Style.RESET_ALL}")
    print(f"Hittade {total_episodes} nya avsnitt från {total_podcasts} podcasts")
    
    # Lista alla nya avsnitt per podcast
    for podcast_name, episodes in new_episodes.items():
        print_subheader(f"{podcast_name} ({len(episodes)} nya avsnitt)")
        
        # Visa alla avsnitt
        for episode in episodes:
            print(f"  • {Fore.WHITE}{episode['title']}{Style.RESET_ALL} ({episode['date']})")
            print(f"    Länk: {Fore.BLUE}{episode['link']}{Style.RESET_ALL}")
    
    # Visa populära aktier denna vecka
    stock_counts = {}
    
    # Gå igenom alla poddavsnitt som analyserats den senaste veckan
    all_results = podcast_api.get_latest_results()
    for podcast_data in all_results:
        for episode in podcast_data.get('episodes', []):
            # Kontrollera om avsnittet är från den senaste veckan
            episode_date = datetime.fromisoformat(episode.get('date')) if 'date' in episode else None
            if episode_date and (datetime.now() - episode_date).days <= 7:
                # Räkna aktieomtal
                stock_analysis = episode.get('stock_analysis', {})
                for mention in stock_analysis.get('mentions', []):
                    stock_name = mention.get('name', '')
                    if stock_name:
                        stock_counts[stock_name] = stock_counts.get(stock_name, 0) + 1
    
    if stock_counts:
        # Sortera efter antal omnämnanden
        sorted_stocks = sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)
        
        print_subheader("Populära aktier denna vecka")
        
        # Visa de 10 populäraste aktierna
        table_data = [(stock, count) for stock, count in sorted_stocks[:10]]
        print(tabulate(table_data, headers=["Aktie", "Antal omnämnanden"], tablefmt="simple"))

def main():
    # Ladda miljövariabler
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
    
    # Argumentparser
    parser = argparse.ArgumentParser(description='Analysera poddar för aktieomtal via Spotify API')
    parser.add_argument('--podcasts', '-p', nargs='+', help='Lista med podcastnamn att analysera')
    parser.add_argument('--episodes', '-e', type=int, default=5, help='Antal avsnitt per podcast att analysera')
    parser.add_argument('--stock', '-s', help='Hämta alla omnämnanden av specifik aktie')
    parser.add_argument('--raw', '-r', action='store_true', help='Visa rådata i JSON-format')
    parser.add_argument('--list', '-l', action='store_true', help='Lista senaste analyserade avsnitt')
    parser.add_argument('--weekly', '-w', action='store_true', help='Generera veckorapport med nya avsnitt')
    parser.add_argument('--check', '-c', type=int, default=7, help='Kontrollera nya avsnitt för antal dagar (standard: 7)')
    args = parser.parse_args()
    
    # Standard poddar om ingen lista anges
    default_podcasts = [
        "Börspodden",
        "Nordnet Sparpodden",
        "Affärsvärlden Analys",
        "Investerarens Podcast",
        "Nextconomy by Danske Bank Sweden",
        "Börsmäklarna",
        "Tillsammans mot miljonen"
    ]
    
    podcasts_to_analyze = args.podcasts if args.podcasts else default_podcasts
    
    # Hämta nycklar från miljövariabler
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not client_id or not client_secret:
        logger.error("Spotify API-nycklar saknas i miljövariabler.")
        print(f"\n{Fore.RED}Spotify API-nycklar saknas! Se till att SPOTIFY_CLIENT_ID och SPOTIFY_CLIENT_SECRET är satta i .env-filen.{Style.RESET_ALL}")
        sys.exit(1)
    
    # Visa varning om OpenAI API-nyckel saknas
    if not openai_api_key:
        print(f"\n{Fore.YELLOW}Varning: OpenAI API-nyckel saknas. Transkribering och avancerad analys kommer inte att fungera.{Style.RESET_ALL}")
    
    # Initiera API-klient
    podcast_api = PodcastAPI(client_id, client_secret, openai_api_key)
    
    # Om vi vill göra en veckorapport
    if args.weekly:
        new_episodes = podcast_api.check_new_episodes(days=args.check)
        print_weekly_report(new_episodes, podcast_api)
        
        # Fråga om användaren vill analysera de nya avsnitten
        if new_episodes:
            print(f"\n{Fore.CYAN}Vill du analysera dessa nya avsnitt? (y/n){Style.RESET_ALL}")
            choice = input().strip().lower()
            
            if choice == 'y' or choice == 'yes':
                # Analysera bara podcasts med nya avsnitt
                podcasts_to_analyze = list(new_episodes.keys())
                print(f"\n{Fore.GREEN}Analyserar nya avsnitt från {len(podcasts_to_analyze)} podcasts...{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.YELLOW}Avbryter analys.{Style.RESET_ALL}")
                return
    
    # Om vi bara vill lista befintliga analysresultat
    if args.list:
        print_header("SENASTE ANALYSERADE PODDAR")
        results = podcast_api.get_latest_results()
        
        if not results:
            print(f"\n{Fore.RED}Inga analysresultat hittades.{Style.RESET_ALL}")
            return
        
        podcasts_table = []
        for podcast_data in results:
            podcast_name = podcast_data.get('podcast_name', 'Okänd')
            analysis_date = datetime.fromisoformat(podcast_data.get('analysis_date')).strftime("%Y-%m-%d %H:%M")
            episodes = podcast_data.get('episodes', [])
            episode_count = len(episodes)
            
            # Räkna totala antalet aktieomtal
            mention_count = 0
            for episode in episodes:
                mention_count += len(episode.get('stock_analysis', {}).get('mentions', []))
            
            podcasts_table.append([podcast_name, analysis_date, episode_count, mention_count])
        
        print(tabulate(podcasts_table, headers=["Podcast", "Analysdatum", "Antal avsnitt", "Antal aktieomtal"], tablefmt="pretty"))
        return
    
    # Om vi ska söka efter en specifik aktie
    if args.stock:
        stock_name = args.stock
        print_header(f"AKTIEOMTAL FÖR {stock_name.upper()}")
        
        print(f"{format_timestamp()} Söker efter omnämnanden av {Fore.YELLOW}{stock_name}{Style.RESET_ALL}...")
        stock_mentions = podcast_api.get_stock_mentions(stock_name)
        
        if stock_mentions:
            print(f"\n{Fore.GREEN}Hittade {len(stock_mentions)} avsnitt med omnämnanden av {stock_name}{Style.RESET_ALL}")
            
            # Visa omnämnanden
            for i, mention_group in enumerate(stock_mentions, 1):
                podcast = mention_group['podcast']
                episode = mention_group['episode']
                date = mention_group['date']
                link = mention_group['link']
                summary = mention_group.get('summary', '')
                
                print_subheader(f"{i}. {podcast} - {episode} ({date})")
                print(f"   Länk: {Fore.BLUE}{link}{Style.RESET_ALL}")
                
                if summary:
                    print(f"\n   {Fore.CYAN}Sammanfattning:{Style.RESET_ALL}")
                    print(f"   {wrap_text(summary)}")
                
                # Visa alla omnämnanden i avsnittet
                print(f"\n   {Fore.CYAN}Aktieomtal:{Style.RESET_ALL}")
                for j, m in enumerate(mention_group['mentions'], 1):
                    print_mention(m, j)
            
            if args.raw:
                print_header("RÅDATA (JSON)")
                print_json_pretty(stock_mentions)
                
        else:
            print(f"\n{Fore.YELLOW}Inga omnämnanden av {stock_name} hittades.{Style.RESET_ALL}")
        
        return
    
    # Annars, analysera poddar
    for podcast_name in podcasts_to_analyze:
        print_header(f"ANALYSERAR {podcast_name.upper()}")
        print(f"{format_timestamp()} Hämtar podcastdata från Spotify...")
        
        results = podcast_api.analyze_podcast(podcast_name, max_episodes=args.episodes)
        
        if results:
            episode_count = len(results["episodes"])
            all_mentions = []
            
            # Räkna alla aktieomtal
            for episode in results["episodes"]:
                mentions = episode.get("stock_analysis", {}).get("mentions", [])
                all_mentions.extend(mentions)
            
            print(f"\n{Fore.GREEN}Analys av {podcast_name} klar:{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}Analyserade avsnitt:{Style.RESET_ALL} {episode_count}")
            print(f"  {Fore.CYAN}Hittade aktieomtal:{Style.RESET_ALL} {len(all_mentions)}")
            
            # Visa resultaten för varje avsnitt
            for episode in results["episodes"]:
                mentions = episode.get("stock_analysis", {}).get("mentions", [])
                print_episode_summary(episode, len(mentions))
                
                # Visa aktieomtal om det finns några
                if mentions:
                    for i, mention in enumerate(mentions, 1):
                        print_mention(mention, i)
            
            # Visa rådata om det begärts
            if args.raw:
                print_header("RÅDATA (JSON)")
                print_json_pretty(results)
                
        else:
            print(f"\n{Fore.RED}Kunde inte analysera {podcast_name}{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}Analys av alla poddar klar!{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Avbruten av användaren.{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}Ett oväntat fel inträffade: {e}{Style.RESET_ALL}")
        logger.exception("Oväntat fel")
        sys.exit(1)