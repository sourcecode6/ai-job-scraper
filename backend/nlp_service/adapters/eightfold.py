import time
import json
import re
import base64
from datetime import datetime
from backend.nlp_service.utils import queue_http, HEADERS

def scrape_eightfold(company, filters):
    # Works for Qualcomm, Microsoft, Ericsson
    base_url = company['eightfoldBaseUrl']
    domain = company['eightfoldDomain']
    search_url = f"{base_url}/api/pcsx/search"

    location_filter = filters.get('locations') or [filters.get('location', 'India')]
    jobs = []

    for loc in location_filter:
        start = 0
        page_size = 10
        total = None

        while True:
            params = {
                "domain": domain,
                "location": loc,
                "query": filters.get('query', ''),
                "start": start,
                "num": page_size
            }

            headers = HEADERS.copy()
            headers.update({
                'Referer': f"{base_url}/careers",
                'Origin': base_url
            })

            res = queue_http(search_url, params=params, headers=headers)
            if res.status_code != 200:
                res.raise_for_status()

            data = res.json().get('data', {})
            positions = data.get('positions', [])
            total = data.get('count', total or 0)

            if not positions:
                break

            for p in positions:
                job_id = p.get('atsJobId') or str(p.get('id'))
                loc_str = ", ".join(p.get('locations', []))
                job_url = f"{base_url}{p.get('positionUrl', '/careers')}"

                jobs.append({
                    "companyName": company['name'],
                    "jobId": str(job_id),
                    "jobTitle": p.get('name', 'Unknown Title'),
                    "location": loc_str,
                    "department": p.get('department', ''),
                    "postedDate": datetime.fromtimestamp(p['postedTs']).isoformat() + 'Z' if p.get('postedTs') else datetime.utcnow().isoformat() + 'Z',
                    "employmentType": "Full-time",
                    "jobDescription": "", # Detail API is not parsed to avoid trigger block
                    "url": job_url,
                    "applyUrl": job_url
                })

            start += len(positions)
            if start >= total or len(positions) < page_size:
                break

    return jobs
