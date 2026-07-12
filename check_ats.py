import requests
import json
from bs4 import BeautifulSoup

def check_ats(url, name):
    print(f"\n--- Checking {name} ({url}) ---")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print("Status Code:", r.status_code)
        
        # Check for redirects
        print("Final URL:", r.url)
        
        html = r.text
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for iframe or specific scripts
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            print("IFRAME found:", src)
            
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'workday' in href.lower() or 'greenhouse' in href.lower() or 'lever' in href.lower() or 'icims' in href.lower() or 'ashby' in href.lower() or 'eightfold' in href.lower() or 'smartrecruiters' in href.lower():
                print("ATS Link found:", href)
                
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    check_ats("https://www.graphcore.ai/careers", "Graphcore")
    check_ats("https://research.samsung.com/careers", "Samsung Research")
