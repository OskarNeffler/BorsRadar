from flask import Flask, request, jsonify
import os
import sys
import json
import logging
from podcast_api import PodcastAPI
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Ladda miljövariabler
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('podcast_api_service.log')
    ]
)

logger = logging.getLogger('podcast_api_service')

# Skapa Flask-appen
app = Flask(__name__)

# Initiera PodcastAPI
client_id = os.getenv('SPOTIFY_CLIENT_ID')
client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
openai_api_key = os.getenv('OPENAI_API_KEY')

if not client_id or not client_secret:
    logger.error("Spotify API-nycklar saknas i miljövariabler.")
    sys.exit(1)

podcast_api = PodcastAPI(client_id, client_secret, openai_api_key)

# Hjälpfunktioner
def is_episode_already_analyzed(episode_id):
    """Kontrollera om ett avsnitt redan har analyserats"""
    results_dir = podcast_api.results_dir
    episode_file = os.path.join(results_dir, f"episode_{episode_id}.json")
    
    if os.path.exists(episode_file):
        return True
        
    # Kontrollera även i alla podcast-filer
    for filename in os.listdir(results_dir):
        if not filename.endswith('.json'):
            continue
            
        filepath = os.path.join(results_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for episode in data.get('episodes', []):
                    if episode.get('id') == episode_id:
                        return True
        except:
            continue
            
    return False

# API-rutter
@app.route('/api/health', methods=['GET'])
def health_check():
    """Kontrollera att API:et fungerar"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/podcasts', methods=['GET'])
def get_podcasts():
    """Hämta alla tillgängliga podcasts"""
    podcasts = []
    for name, pod_id in podcast_api.podcast_ids.items():
        podcasts.append({"name": name, "id": pod_id})
    
    return jsonify({"podcasts": podcasts})

@app.route('/api/podcasts/<podcast_name>/episodes', methods=['GET'])
def get_episodes(podcast_name):
    """Hämta avsnitt för en specifik podcast"""
    max_episodes = request.args.get('max', default=5, type=int)
    
    podcast_id = podcast_api.get_podcast_id(podcast_name)
    if not podcast_id:
        return jsonify({"error": "Podcast hittades inte"}), 404
        
    episodes = podcast_api.get_podcast_episodes(podcast_id, max_episodes=max_episodes)
    
    # Lägg till information om avsnitt redan är analyserade
    for episode in episodes:
        episode['is_analyzed'] = is_episode_already_analyzed(episode['id'])
    
    return jsonify({"podcast": podcast_name, "episodes": episodes})

@app.route('/api/analyze/podcast', methods=['POST'])
def analyze_podcast():
    """Analysera en specifik podcast"""
    data = request.json
    
    if not data or 'podcast_name' not in data:
        return jsonify({"error": "podcast_name måste anges"}), 400
        
    podcast_name = data['podcast_name']
    max_episodes = data.get('max_episodes', 5)
    avoid_transcription = data.get('avoid_transcription', False)
    skip_analyzed = data.get('skip_analyzed', True)
    
    # Hämta podcast-ID
    podcast_id = podcast_api.get_podcast_id(podcast_name)
    if not podcast_id:
        return jsonify({"error": f"Kunde inte hitta podcast: {podcast_name}"}), 404
        
    # Hämta episoder
    episodes = podcast_api.get_podcast_episodes(podcast_id, max_episodes=max_episodes)
    
    # Filtrera ut redan analyserade avsnitt om skip_analyzed är True
    if skip_analyzed:
        episodes = [ep for ep in episodes if not is_episode_already_analyzed(ep['id'])]
        
    if not episodes:
        return jsonify({"message": f"Inga nya avsnitt att analysera för {podcast_name}"}), 200
    
    # Analysera podcast
    results = podcast_api.analyze_podcast(podcast_name, episodes=episodes, avoid_transcription=avoid_transcription)
    
    if not results:
        return jsonify({"error": f"Kunde inte analysera podcast: {podcast_name}"}), 500
        
    # Extrahera relevant information för svaret
    episodes_info = []
    for episode in results['episodes']:
        mentions_count = len(episode.get('stock_analysis', {}).get('mentions', []))
        
        episodes_info.append({
            "id": episode['id'],
            "title": episode['title'],
            "date": episode['date'],
            "has_transcript": episode.get('has_transcript', False),
            "mentions_count": mentions_count
        })
    
    return jsonify({
        "podcast_name": podcast_name,
        "analysis_date": results['analysis_date'],
        "episodes_analyzed": len(episodes_info),
        "episodes": episodes_info
    })

@app.route('/api/analyze/episode/<episode_id>', methods=['POST'])
def analyze_episode(episode_id):
    """Analysera ett specifikt avsnitt"""
    data = request.json
    podcast_name = data.get('podcast_name', None)
    avoid_transcription = data.get('avoid_transcription', False)
    
    # Kontrollera om avsnittet redan analyserats
    if is_episode_already_analyzed(episode_id):
        return jsonify({"message": "Avsnittet är redan analyserat", "episode_id": episode_id}), 200
    
    # Hämta episodinformation från Spotify
    headers = {
        'Authorization': f'Bearer {podcast_api.get_access_token()}'
    }
    
    # Om podcast_name anges, sök episoden i den podcasten
    if podcast_name:
        podcast_id = podcast_api.get_podcast_id(podcast_name)
        if not podcast_id:
            return jsonify({"error": f"Kunde inte hitta podcast: {podcast_name}"}), 404
            
        episodes = podcast_api.get_podcast_episodes(podcast_id, max_episodes=50)
        episode = next((ep for ep in episodes if ep['id'] == episode_id), None)
        
        if not episode:
            return jsonify({"error": f"Kunde inte hitta avsnitt med ID {episode_id} i podcast {podcast_name}"}), 404
    else:
        # Hämta episoden direkt med ID
        try:
            episode_url = f'https://api.spotify.com/v1/episodes/{episode_id}?market=SE'
            response = requests.get(episode_url, headers=headers)
            response.raise_for_status()
            episode = response.json()
        except Exception as e:
            return jsonify({"error": f"Kunde inte hämta avsnitt: {str(e)}"}), 404
    
    # Analysera avsnittet
    results = podcast_api.analyze_single_episode(episode, avoid_transcription=avoid_transcription)
    
    if not results:
        return jsonify({"error": f"Kunde inte analysera avsnitt: {episode_id}"}), 500
    
    # Spara resultatet separat för detta avsnitt
    episode_file = os.path.join(podcast_api.results_dir, f"episode_{episode_id}.json")
    with open(episode_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    return jsonify({
        "episode_id": episode_id,
        "title": results.get('title', ''),
        "date": results.get('date', ''),
        "has_transcript": results.get('has_transcript', False),
        "mentions_count": len(results.get('stock_analysis', {}).get('mentions', []))
    })

@app.route('/api/results/podcast/<podcast_name>', methods=['GET'])
def get_podcast_results(podcast_name):
    """Hämta analysresultat för en specifik podcast"""
    results = podcast_api.get_latest_results(podcast_name)
    
    if not results:
        return jsonify({"error": f"Inga resultat hittades för podcast: {podcast_name}"}), 404
        
    return jsonify(results)

@app.route('/api/results/episode/<episode_id>', methods=['GET'])
def get_episode_results(episode_id):
    """Hämta analysresultat för ett specifikt avsnitt"""
    # Först kolla om det finns en separat fil för avsnittet
    episode_file = os.path.join(podcast_api.results_dir, f"episode_{episode_id}.json")
    
    if os.path.exists(episode_file):
        with open(episode_file, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    
    # Annars sök i alla podcast-filer
    all_results = podcast_api.get_latest_results()
    
    for podcast_data in all_results:
        for episode in podcast_data.get('episodes', []):
            if episode.get('id') == episode_id:
                return jsonify(episode)
                
    return jsonify({"error": f"Inga resultat hittades för avsnitt: {episode_id}"}), 404

@app.route('/api/stock/<stock_name>', methods=['GET'])
def get_stock_mentions(stock_name):
    """Hämta omnämnanden av en specifik aktie"""
    days = request.args.get('days', default=None, type=int)
    
    mentions = podcast_api.get_stock_mentions(stock_name)
    
    if days:
        # Filtrera resultat efter datum
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_mentions = []
        
        for mention in mentions:
            try:
                episode_date = datetime.fromisoformat(mention.get('date'))
                if episode_date >= cutoff_date:
                    filtered_mentions.append(mention)
            except (ValueError, TypeError):
                # Om datumet inte kan tolkas, skippa filtrering för det omnämnandet
                filtered_mentions.append(mention)
                
        mentions = filtered_mentions
    
    if not mentions:
        return jsonify({"message": f"Inga omnämnanden av {stock_name} hittades"}), 200
        
    return jsonify({"stock": stock_name, "mentions": mentions})

@app.route('/api/check/new-episodes', methods=['GET'])
def check_new_episodes():
    """Kontrollera nya avsnitt för alla podcasts"""
    days = request.args.get('days', default=14, type=int)
    
    new_episodes = podcast_api.check_new_episodes(days=days)
    
    return jsonify({
        "days_checked": days,
        "new_episodes": new_episodes,
        "podcast_count": len(new_episodes),
        "episode_count": sum(len(episodes) for episodes in new_episodes.values())
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)