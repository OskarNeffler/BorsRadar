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