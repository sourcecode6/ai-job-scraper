import requests
import json
from datetime import datetime
from backend.nlp_service.utils import queue_http, HEADERS

def scrape_ashbyhq(company, filters):
    board_token = company.get('board_token')
    if not board_token:
        raise ValueError(f"Missing board_token for {company['name']}")

    search_url = f"https://api.ashbyhq.com/posting-api/job-board/{board_token}?includeMultipleLocations=true"
    jobs = []

    res = queue_http(search_url, headers=HEADERS)
    if res.status_code != 200:
        res.raise_for_status()

    data = res.json()
    postings = data.get('jobs', [])

    locations_filter = filters.get('locations') or ([filters.get('location')] if filters.get('location') else [])

    for p in postings:
        loc = p.get('location', '')
        
        if locations_filter:
            loc_lower = loc.lower()
            matched = False
            for filter_loc in locations_filter:
                if filter_loc.lower() in loc_lower:
                    matched = True
                    break
            if not matched:
                continue

        job_id = p.get('id')
        title = p.get('title', 'Unknown Title')
        
        # Ashby provides descriptionPlain out of the box!
        desc = p.get('descriptionPlain', '')
        if not desc:
            desc = p.get('descriptionHtml', '') # Fallback

        published_at = p.get('publishedAt', datetime.utcnow().isoformat() + 'Z')

        jobs.append({
            "companyName": company['name'],
            "jobId": str(job_id),
            "jobTitle": title,
            "location": loc,
            "department": p.get('department', ''),
            "postedDate": published_at,
            "employmentType": p.get('employmentType', 'Full-time'),
            "jobDescription": desc,
            "url": p.get('jobUrl', ''),
            "applyUrl": p.get('applyUrl', '')
        })

    return jobs
