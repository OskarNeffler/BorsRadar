import requests
import json
import os
import re
from config import OPENAI_API_KEY, GOOGLE_API_KEY

class BaseAIAnalyzer:
    """
    Basklass för AI-analys och chatbottjänster
    """
    def analyze_text(self, text):
        """
        Grundläggande metod för textanalys
        
        :param text: Text att analysera
        :return: Analysresultat
        """
        raise NotImplementedError("Subklasser måste implementera denna metod")
    
    def chat(self, message, session_id=None, context=None):
        """
        Grundläggande chattmetod
        
        :param message: Användarmeddelande
        :param session_id: Valfri sessions-ID
        :param context: Valfri kontext
        :return: Chattsvar
        """
        raise NotImplementedError("Subklasser måste implementera denna metod")
    
    def find_related_content(self, content_items, content_type):
        """
        Hitta relaterade innehållsobjekt baserat på ämne
        
        :param content_items: Lista med innehållsobjekt (nyheter, podcasts)
        :param content_type: Typ av innehåll ("news", "podcast", "mixed")
        :return: Grupperade innehållsobjekt baserat på ämne
        """
        raise NotImplementedError("Subklasser måste implementera denna metod")

class OpenAIAnalyzer(BaseAIAnalyzer):
    """
    OpenAI-implementering för textanalys och chattjänster
    """
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.api_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def analyze_text(self, text):
        """
        Analysera text med OpenAI för att extrahera företagsomtal, sentiment och nyckelinformation
        
        :param text: Text att analysera
        :return: Analysresultat
        """
        try:
            prompt = f"""
            Analysera följande text och extrahera:
            1. Företagsomtal (med ticker om möjligt)
            2. Övergripande sentiment (-1 till 1 skala)
            3. En kort sammanfattning
            4. Nyckelämnen
            5. Kategorier
            
            Text: {text}
            
            Svara som ett JSON-objekt med nycklarna: 
            "entities", "sentiment", "summary", "key_topics", "categories".
            
            För enheter, inkludera en lista med objekt som har "name", "type", 
            "ticker" (om tillgänglig) och "confidence".
            """
            
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system", 
                        "content": "Du är en avancerad finansiell analysassistent som extraherar strukturerad data från text."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                return json.loads(response_data['choices'][0]['message']['content'])
            else:
                print(f"API-förfrågan misslyckades: {response.text}")
                return self._fallback_analysis(text)
        
        except Exception as e:
            print(f"Fel vid textanalys: {str(e)}")
            return self._fallback_analysis(text)
    
    def _fallback_analysis(self, text):
        """
        Reservanalys om huvudmetoden misslyckas
        
        :param text: Text att analysera
        :return: Grundläggande analysresultat
        """
        return {
            "entities": [],
            "sentiment": {"score": 0},
            "summary": self._generate_simple_summary(text),
            "key_topics": [],
            "categories": []
        }
    
    def _generate_simple_summary(self, text, max_length=200):
        """
        Generera en enkel sammanfattning av texten
        
        :param text: Text att sammanfatta
        :param max_length: Maximal längd på sammanfattningen
        :return: Sammanfattning
        """
        # Dela texten i meningar
        sentences = re.split(r'[.!?]', text)
        
        # Välj de två första meningarna som inte är för korta
        summary_sentences = [
            sentence.strip() for sentence in sentences 
            if len(sentence.strip()) > 30
        ][:2]
        
        summary = '. '.join(summary_sentences)
        return summary[:max_length] + '...' if len(summary) > max_length else summary
    
    def chat(self, message, session_id=None, context=None):
        """
        Chatta med OpenAI och få ett svar
        
        :param message: Användarmeddelande
        :param session_id: Valfri sessions-ID
        :param context: Valfri kontext
        :return: Chattsvar
        """
        try:
            # Förbereda meddelanden med historik
            messages = [
                {
                    "role": "system", 
                    "content": "Du är en professionell finansiell assistent som hjälper användare med "
                               "insikter om aktier, företag, investeringar och ekonomiska nyheter. "
                               "Svara koncist och informativt på svenska."
                }
            ]
            
            # Lägg till tidigare konversationshistorik om den finns
            if context and 'chat_history' in context:
                for msg in context['chat_history']:
                    role = "user" if msg["is_user"] else "assistant"
                    messages.append({"role": role, "content": msg["content"]})
            
            # Lägg till nuvarande meddelande
            messages.append({"role": "user", "content": message})
            
            payload = {
                "model": "gpt-4o",
                "messages": messages,
                "temperature": 0.7
            }
            
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                bot_response = response_data['choices'][0]['message']['content']
                
                # Analysera svaret för företagsomtal
                analysis = self.analyze_text(message + "\n" + bot_response)
                
                return {
                    "response": bot_response,
                    "entities": analysis.get("entities", []),
                    "sentiment": analysis.get("sentiment", {"score": 0})
                }
            else:
                return {
                    "response": "Jag kunde inte behandla din förfrågan just nu. Försök igen senare.",
                    "entities": [],
                    "sentiment": {"score": 0}
                }
        
        except Exception as e:
            print(f"Fel vid chatthantering: {str(e)}")
            return {
                "response": "Ett oväntat fel inträffade. Vänligen försök igen.",
                "entities": [],
                "sentiment": {"score": 0}
            }
    
    def find_related_content(self, content_items, content_type="mixed"):
        """
        Hitta relaterat innehåll genom att gruppera innehåll baserat på ämne med hjälp av OpenAI
        
        :param content_items: Lista med innehållsobjekt (nyheter, podcasts, episoder)
        :param content_type: Typ av innehåll ("news", "podcast", "mixed")
        :return: Grupperade innehållsobjekt baserat på ämne
        """
        try:
            # Förbered data för analys
            content_data = []
            for item in content_items:
                if content_type == "news" or (content_type == "mixed" and "title" in item and "content" in item):
                    # För nyheter
                    content_data.append({
                        "id": item.get("id"),
                        "type": "news",
                        "title": item.get("title", ""),
                        "content": item.get("content", ""),
                        "summary": item.get("summary", ""),
                        "published_at": item.get("published_at", "")
                    })
                elif content_type == "podcast" or (content_type == "mixed" and "title" in item and "description" in item):
                    # För podcast-episoder
                    content_data.append({
                        "id": item.get("id"),
                        "type": "podcast",
                        "title": item.get("title", ""),
                        "content": item.get("description", "") + " " + (item.get("summary", "")),
                        "published_at": item.get("published_at", "")
                    })
            
            # Om innehållslistan är för stor, begränsa den
            if len(content_data) > 30:
                # Begränsa till 30 objekt för att undvika token-begränsningar och kostnader
                content_data = content_data[:30]
            
            # Skapa en prompt för att gruppera innehållet
            prompt = f"""
            Här är en lista med {len(content_data)} innehållsobjekt (nyheter och/eller podcast-episoder).
            Gruppera dem baserat på relaterat ämne och identifiera huvudämnet för varje grupp.
            
            Innehåll:
            {json.dumps(content_data, ensure_ascii=False, indent=2)}
            
            Svara med ett JSON-objekt där varje nyckel är ett unikt ämne-ID och varje värde 
            är ett objekt med:
            1. "topic" - huvudämnet för gruppen
            2. "items" - en lista med ID:n för innehållsobjekt som tillhör gruppen
            3. "summary" - en kort sammanfattning av ämnet
            4. "keywords" - nyckelord för detta ämne (max 5)
            
            Exempel:
            {{
              "topic_1": {{
                "topic": "Tesla Q4 Earnings",
                "items": [1, 5, 8],
                "summary": "Tesla's fourth quarter earnings report and market reaction",
                "keywords": ["Tesla", "Earnings", "Q4", "EV", "Stock"]
              }},
              "topic_2": {{
                "topic": "Inflation Concerns",
                "items": [2, 3, 7],
                "summary": "Rising inflation and central bank responses",
                "keywords": ["Inflation", "Fed", "Interest Rates", "Economy"]
              }}
            }}
            
            Varje innehållsobjekt bör tillhöra exakt en grupp. Skapa inte för många grupper - 
            försök konsolidera liknande ämnen.
            """
            
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system", 
                        "content": "Du är en avancerad innehållsanalytiker som identifierar relaterade ämnen och grupperar innehåll."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                topic_groups = json.loads(response_data['choices'][0]['message']['content'])
                
                # Konvertera ID-listor till faktiska innehållsobjekt
                id_to_content = {item.get("id"): item for item in content_items if "id" in item}
                
                for topic_id, topic_data in topic_groups.items():
                    # Ersätt ID-listan med en lista av faktiska innehållsobjekt
                    content_ids = topic_data.get("items", [])
                    topic_data["items"] = [id_to_content.get(item_id) for item_id in content_ids if item_id in id_to_content]
                
                return topic_groups
            else:
                print(f"API-förfrågan misslyckades vid gruppering: {response.text}")
                return self._fallback_grouping(content_items)
        
        except Exception as e:
            print(f"Fel vid gruppering av innehåll: {str(e)}")
            return self._fallback_grouping(content_items)
    
    def _fallback_grouping(self, content_items):
        """
        Enkel reservgruppering om huvudmetoden misslyckas
        
        :param content_items: Lista med innehållsobjekt
        :return: Enkel gruppering (allt i en grupp)
        """
        return {
            "topic_1": {
                "topic": "Alla objekt",
                "items": content_items,
                "summary": "Alla innehållsobjekt (reservgruppering)",
                "keywords": ["Finans", "Företag", "Ekonomi"]
            }
        }
    
    def search_and_analyze(self, query, content_items, max_results=10):
        """
        Söker och analyserar innehåll baserat på en sökfråga
        
        :param query: Användarens sökfråga
        :param content_items: Lista med innehållsobjekt att söka igenom
        :param max_results: Maximalt antal resultat att returnera
        :return: Rankade sökresultat med analys
        """
        try:
            # Förbered data för sökning
            search_data = []
            for item in content_items:
                # Skapa en sökbar sammanfattning för varje objekt
                content_type = "news" if "content" in item else "podcast"
                text_content = item.get("content", "") if content_type == "news" else item.get("description", "") + " " + item.get("summary", "")
                
                search_data.append({
                    "id": item.get("id"),
                    "type": content_type,
                    "title": item.get("title", ""),
                    "content": text_content[:1000] if len(text_content) > 1000 else text_content,  # Begränsa längden
                    "published_at": item.get("published_at", "")
                })
            
            # Begränsa söktexten om den är för stor
            if len(search_data) > 50:
                search_data = search_data[:50]
            
            # Skapa en prompt för sökning
            prompt = f"""
            Sökfråga: "{query}"
            
            Hitta de mest relevanta resultaten från följande innehållslista baserat på sökfrågan.
            Ranka resultaten efter relevans och presentera max {max_results} resultat.
            
            Innehåll att söka igenom:
            {json.dumps(search_data, ensure_ascii=False, indent=2)}
            
            Svara med ett JSON-objekt med följande format:
            {{
              "results": [
                {{
                  "id": [innehålls-ID],
                  "type": [typ av innehåll],
                  "relevance_score": [0-100 poäng för relevans],
                  "match_reason": [kort förklaring till varför detta är relevant]
                }},
                ...
              ],
              "query_analysis": {{
                "interpreted_as": [tolkning av sökfrågan],
                "suggested_topics": [relaterade ämnen att utforska],
                "suggested_filters": [föreslagna filter för sökningen]
              }}
            }}
            """
            
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system", 
                        "content": "Du är en avancerad sökagorithm som hittar och rankar relevanta resultat."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                search_results = json.loads(response_data['choices'][0]['message']['content'])
                
                # Konvertera resultat-ID:n till faktiska innehållsobjekt
                id_to_content = {item.get("id"): item for item in content_items if "id" in item}
                
                for result in search_results.get("results", []):
                    content_id = result.get("id")
                    if content_id in id_to_content:
                        result["content"] = id_to_content[content_id]
                
                return search_results
            else:
                print(f"API-förfrågan misslyckades vid sökning: {response.text}")
                return self._fallback_search(query, content_items, max_results)
        
        except Exception as e:
            print(f"Fel vid sökning och analys: {str(e)}")
            return self._fallback_search(query, content_items, max_results)
    
    def _fallback_search(self, query, content_items, max_results=10):
        """
        Enkel reservsökning om huvudmetoden misslyckas
        
        :param query: Användarens sökfråga
        :param content_items: Lista med innehållsobjekt
        :param max_results: Maximalt antal resultat
        :return: Enkla sökresultat
        """
        # Simpel sökning efter ord i titlar
        query_terms = query.lower().split()
        results = []
        
        for item in content_items:
            title = item.get("title", "").lower()
            matches = sum(1 for term in query_terms if term in title)
            if matches > 0:
                results.append({
                    "id": item.get("id"),
                    "type": "news" if "content" in item else "podcast",
                    "relevance_score": matches * 10,
                    "match_reason": "Enkel textmatchning",
                    "content": item
                })
        
        # Sortera efter antal matchningar och begränsa resultaten
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = results[:max_results] if len(results) > max_results else results
        
        return {
            "results": results,
            "query_analysis": {
                "interpreted_as": query,
                "suggested_topics": [],
                "suggested_filters": []
            }
        }

class GoogleVertexAIAnalyzer(BaseAIAnalyzer):
    """
    Google Vertex AI-implementering som ett alternativ
    """
    def __init__(self):
        self.api_key = GOOGLE_API_KEY
        # Implementera liknande metoder som OpenAIAnalyzer
        # (kodad förenklad för brevitets skull)
        pass

def get_chatbot_api():
    """
    Hämta standard chatbot-API
    
    :return: Chatbot-instans
    """
    # Standardval är OpenAI
    return OpenAIAnalyzer()

# Alias för bakåtkompatibilitet
ChatbotAPI = get_chatbot_api