import time
import json
import re
import base64
from datetime import datetime
from backend.nlp_service.utils import queue_http, HEADERS, http_session

def get_cisco_csrf():
    res = queue_http('https://careers.cisco.com/global/en/search-results')
    if res.status_code != 200:
        res.raise_for_status()

    play_session = None
    if 'PLAY_SESSION' in res.cookies:
        play_session = res.cookies.get('PLAY_SESSION')
    
    if not play_session:
        for c in http_session.cookies:
            if c.name == 'PLAY_SESSION' and 'cisco.com' in c.domain:
                play_session = c.value
                break
    
    # Just forward all session cookies to subsequent requests
    cookie_header = "; ".join([f"{k}={v}" for k, v in http_session.cookies.items()])

    if not play_session:
        raise Exception("PLAY_SESSION cookie not found")

    parts = play_session.split('.')
    if len(parts) < 2:
        raise Exception("Invalid PLAY_SESSION JWT format")

    # Add base64 padding if needed
    payload_b64 = parts[1]
    payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
    payload_json = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
    csrf_token = payload_json.get('data', {}).get('csrfToken')

    if not csrf_token:
        raise Exception("CSRF token not found in PLAY_SESSION")

    return cookie_header, csrf_token

def scrape_cisco(company, filters):
    # Works for Cisco
    locations = filters.get('locations') or [filters.get('location', 'India')]
    keywords = filters.get('keywords', 'engineer')

    jobs = []
    from_offset = 0
    page_size = 25

    cookie_header, csrf_token = get_cisco_csrf()

    while True:
        body = {
            "sortBy": "",
            "subsearch": "",
            "from": from_offset,
            "jobs": True,
            "counts": False,
            "all_fields": [],
            "pageName": "search-results",
            "size": page_size,
            "clearAll": False,
            "jdsource": "facets",
            "isSliderEnable": False,
            "pageId": "page4",
            "siteType": "external",
            "keywords": keywords,
            "global": True,
            "selected_fields": {
                "country": locations
            },
            "lang": "en_global",
            "deviceType": "desktop",
            "country": "global",
            "refNum": "CISCISGLOBAL",
            "ddoKey": "refineSearch"
        }

        headers = HEADERS.copy()
        headers.update({
            'Content-Type': 'application/json',
            'Referer': 'https://careers.cisco.com/global/en/search-results',
            'x-csrf-token': csrf_token,
            'Cookie': cookie_header
        })

        res = queue_http('https://careers.cisco.com/widgets', method='POST', json=body, headers=headers)
        if res.status_code != 200:
            res.raise_for_status()

        result = res.json().get('refineSearch', {})
        if not result or result.get('status') != 200:
            break

        page_jobs = result.get('data', {}).get('jobs', [])
        if not page_jobs:
            break

        for j in page_jobs:
            job_id = j.get('jobId') or j.get('reqId') or j.get('jobSeqNo') or str(int(time.time()))
            loc = j.get('location') or ", ".join(filter(None, [j.get('city'), j.get('state'), j.get('country')]))
            job_url = j.get('applyUrl') or f"https://careers.cisco.com/global/en/job/{job_id}"

            jobs.append({
                "companyName": company['name'],
                "jobId": str(job_id),
                "jobTitle": j.get('title', 'Unknown Title'),
                "location": loc,
                "department": j.get('category') or j.get('department') or '',
                "postedDate": j.get('postedDate') or j.get('dateCreated') or datetime.utcnow().isoformat() + 'Z',
                "employmentType": j.get('type', 'Full-time'),
                "jobDescription": j.get('descriptionTeaser', ''),
                "url": job_url,
                "applyUrl": j.get('applyUrl') or job_url
            })

        from_offset += len(page_jobs)
        if len(page_jobs) < page_size:
            break

    return jobs
