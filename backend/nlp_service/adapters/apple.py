import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from utils import HEADERS, is_allowed

def scrape_apple(company, filters):
    # Base search URL
    target_url = "https://jobs.apple.com/en-us/search"
    
    # 1. Compliance check
    if not is_allowed(target_url):
        print(f"[{company['name']}] robots.txt forbids scraping {target_url}")
        return []

    jobs = []
    location_filter = filters.get('location', 'India')
    # Convert 'India' to Apple's query param if possible, or just search normally and filter post-scrape
    if location_filter.lower() == 'india':
        search_url = f"{target_url}?location=india-IND"
    else:
        # Default fallback
        search_url = target_url

    print(f"[{company['name']}] Launching Playwright to scrape {search_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Pass the global User-Agent from utils.HEADERS
        context = browser.new_context(user_agent=HEADERS['User-Agent'])
        page = context.new_page()

        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            
            # Instead of waiting for a specific tbody, wait for networkidle
            # and extract all links that contain /details/
            page.wait_for_timeout(3000) # give a little time for react to render
            
            links = page.evaluate('''() => {
                const anchors = Array.from(document.querySelectorAll('a'));
                return anchors.filter(a => a.href.includes('/details/')).map(a => ({href: a.href, text: a.innerText}));
            }''')
            
            # Remove duplicates based on URL
            unique_links = {l['href']: l['text'] for l in links}
            
            for job_url, title in unique_links.items():
                if not title.strip() or title == "Where we're hiring":
                    continue
                
                title = title.strip()
                
                # Extract job ID from URL
                job_id = job_url.split('/')[-1] if '/' in job_url else str(int(time.time()))
                
                # Apple doesn't show descriptions easily on the main page, so we will use title as description
                # or fetch each page (too slow/risky). We'll stick to title for NLP.
                desc = title
                
                jobs.append({
                    "companyName": company['name'],
                    "jobId": str(job_id),
                    "jobTitle": title,
                    "location": location_filter,
                    "department": '',
                    "postedDate": datetime.utcnow().isoformat() + 'Z',
                    "employmentType": "Full-time",
                    "jobDescription": desc,
                    "url": job_url,
                    "applyUrl": job_url
                })
        except Exception as e:
            print(f"[{company['name']}] Playwright scraping error: {e}")
        finally:
            browser.close()

    return jobs
