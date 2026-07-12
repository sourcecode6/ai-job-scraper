import time
import json
from datetime import datetime
from utils import queue_http, HEADERS

def scrape_eightfold_v2(company, filters):
    base_url = company['eightfoldBaseUrl']
    domain = company['eightfoldDomain']
    search_url = f"{base_url}/api/apply/v2/jobs"

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

            data = res.json()
            
            # The v2 API returns the jobs either in data.positions or just as the list if it's the root array
            positions = data.get('positions', [])
            total = data.get('count', total or 0)

            if not positions:
                break

            for p in positions:
                job_id = p.get('atsJobId') or str(p.get('id'))
                loc_str = ", ".join(p.get('locations', [])) if isinstance(p.get('locations'), list) else p.get('location', '')
                job_url = p.get('canonicalPositionUrl') or f"{base_url}/careers/job/{p.get('id')}"

                jobs.append({
                    "companyName": company['name'],
                    "jobId": str(job_id),
                    "jobTitle": p.get('name', 'Unknown Title'),
                    "location": loc_str,
                    "department": p.get('department', ''),
                    "postedDate": datetime.fromtimestamp(p['t_create']).isoformat() + 'Z' if p.get('t_create') else datetime.utcnow().isoformat() + 'Z',
                    "employmentType": "Full-time",
                    "jobDescription": p.get('job_description', ''),
                    "url": job_url,
                    "applyUrl": job_url
                })

            start += len(positions)
            if start >= total or len(positions) < page_size:
                break

    return jobs
