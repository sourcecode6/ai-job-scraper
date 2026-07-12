import time
import json
import re
import base64
from datetime import datetime
from utils import queue_http, HEADERS

def scrape_arm(company, filters):
    from bs4 import BeautifulSoup
    jobs = []
    page = 1
    has_more = True
    locations_filter = filters.get('locations')

    while has_more:
        url = f"https://careers.arm.com/search-jobs?p={page}"
        res = queue_http(url)
        if res.status_code != 200:
            break

        soup = BeautifulSoup(res.text, 'html.parser')
        ul = soup.find('ul', id='search-results-jobs')
        if not ul:
            break

        cards = ul.find_all('li', class_='job-card')
        if not cards:
            break

        for card in cards:
            a_tag = card.find('a', class_='job-card__title')
            if not a_tag:
                continue

            job_id = a_tag.get('data-job-id') or a_tag.get('href', '').split('/')[-1]
            title = a_tag.text.strip()
            href = a_tag.get('href', '')
            job_url = f"https://careers.arm.com{href}" if href.startswith('/') else href

            loc_span = card.find('span', class_='location')
            loc = loc_span.text.strip() if loc_span else 'Not specified'

            if locations_filter:
                loc_lower = loc.lower()
                matched = False
                for filter_loc in locations_filter:
                    if filter_loc.lower() in loc_lower:
                        matched = True
                        break
                if not matched:
                    continue

            cat_span = card.find('span', class_='category')
            category = cat_span.text.strip() if cat_span else ''

            intro_span = card.find('span', class_='job-card__intro')
            desc = intro_span.text.strip() if intro_span else ''

            jobs.append({
                "companyName": company['name'],
                "jobId": str(job_id),
                "jobTitle": title,
                "location": loc,
                "department": category,
                "postedDate": datetime.utcnow().isoformat() + 'Z',
                "employmentType": "Full-time",
                "jobDescription": desc,
                "url": job_url,
                "applyUrl": job_url
            })

        next_btn = soup.find('a', class_='next')
        if not next_btn or '/search-jobs&p=' not in next_btn.get('href', '') and '?p=' not in next_btn.get('href', '') and f"p={page+1}" not in next_btn.get('href', ''):
            total_count = int(ul.get('data-results-count') or 0)
            if len(jobs) >= total_count:
                has_more = False
                break

        page += 1

    return jobs
