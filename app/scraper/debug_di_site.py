import requests
from bs4 import BeautifulSoup
import os

def debug_di_site():
    # URL vi vill skrapa
    base_url = "https://www.di.se/bors/nyheter/"
    
    # Headers för att simulera en webbläsare
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"Försöker hämta innehåll från {base_url}...")
    
    try:
        # Hämta webbsidan
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        print(f"✅ Lyckades hämta webbsidan! Status code: {response.status_code}")
        
        # Spara HTML-innehållet för inspektion
        with open("di_debug.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"✅ Sparade HTML-innehållet till di_debug.html")
        
        # Analysera HTML med BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug-information: Leta efter möjliga artikelelement
        print("\n----- Möjliga artikelelement -----")
        
        # Testa olika vanliga selektorer för artiklar
        selectors_to_test = [
            'article', '.article', '.news-item', '.di-article',
            '.news-article', '.teaser', '.item', '.news',
            '.di_teaser', 'div[class*="article"]', 'div[class*="teaser"]',
            'div[class*="news"]', 'a[href*="/nyheter/"]'
        ]
        
        for selector in selectors_to_test:
            elements = soup.select(selector)
            if elements:
                print(f"Hittade {len(elements)} element med selektorn '{selector}'")
                # Visa första elementets klassnamn om det finns
                if hasattr(elements[0], 'class'):
                    print(f"  Första elementets klasser: {elements[0].get('class')}")
                
                # Försök hitta en titel inom elementet
                title_elements = elements[0].select('h1, h2, h3, h4, .title, .headline')
                if title_elements:
                    print(f"  Titel: {title_elements[0].text.strip()}")
                
                # Försök hitta en länk inom elementet
                link_elements = elements[0].select('a')
                if link_elements and 'href' in link_elements[0].attrs:
                    print(f"  Länk: {link_elements[0]['href']}")
                
                print()
        
        # Leta efter alla h2- och h3-element som kan vara artikeltitlar
        print("\n----- Möjliga artikeltitlar -----")
        h_elements = soup.select('h1, h2, h3')
        for i, element in enumerate(h_elements[:5]):  # Visa bara de första 5
            print(f"H-element {i+1}:")
            print(f"  Text: {element.text.strip()}")
            print(f"  Förälderelement: {element.parent.name}")
            if hasattr(element.parent, 'class'):
                print(f"  Förälderelement klasser: {element.parent.get('class')}")
            print()
        
        # Leta efter alla a-element som kan innehålla länkar till artiklar
        print("\n----- Möjliga artikellänkar -----")
        a_elements = soup.select('a[href*="/nyheter/"]')
        for i, element in enumerate(a_elements[:5]):  # Visa bara de första 5
            print(f"Länk {i+1}:")
            print(f"  Href: {element['href']}")
            print(f"  Text: {element.text.strip() if element.text.strip() else '[Ingen text]'}")
            if hasattr(element, 'class'):
                print(f"  Klasser: {element.get('class')}")
            print()
        
        print("\nFärdig med debuggning! Använd informationen ovan för att uppdatera skrapern.")
        
    except Exception as e:
        print(f"❌ Fel vid skrapning: {e}")

if __name__ == "__main__":
    debug_di_site()