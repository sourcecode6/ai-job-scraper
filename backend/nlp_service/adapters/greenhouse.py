import time
import json
import re
import html
from datetime import datetime
from backend.nlp_service.utils import queue_http

def scrape_greenhouse(company, filters):
    board_token = company.get('board_token')
    if not board_token:
        print(f"[{company['name']}] Missing board_token in config")
        return []

    # ?content=true includes job descriptions
    endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    
    res = queue_http(endpoint)
    if res.status_code != 200:
        res.raise_for_status()

    data = res.json()
    api_jobs = data.get('jobs', [])
    jobs = []
    
    locations_filter = filters.get('locations') or ([filters.get('location')] if filters.get('location') else [])

    for j in api_jobs:
        loc = j.get('location', {}).get('name', '')
        
        # apply location filter if exists
        if locations_filter:
            loc_lower = loc.lower()
            matched = False
            for filter_loc in locations_filter:
                if filter_loc.lower() in loc_lower:
                    matched = True
                    break
            if not matched:
                continue

        job_id = j.get('id', str(int(time.time())))
        title = j.get('title', 'Unknown Title')
        job_url = j.get('absolute_url', '')
        desc_html = j.get('content', '')
        
        # simple html tag removal for description
        desc_text = re.sub(r'<[^>]+>', ' ', desc_html)
        desc_text = html.unescape(desc_text).strip()

        jobs.append({
            "companyName": company['name'],
            "jobId": str(job_id),
            "jobTitle": title,
            "location": loc,
            "department": '',
            "postedDate": j.get('updated_at') or datetime.utcnow().isoformat() + 'Z',
            "employmentType": "Full-time",
            "jobDescription": desc_text,
            "url": job_url,
            "applyUrl": job_url
        })

    return jobs
