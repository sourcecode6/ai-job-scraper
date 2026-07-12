import time
import json
import re
import base64
from datetime import datetime
from utils import queue_http, HEADERS

def scrape_amd(company, filters):
    # Works for AMD
    locations = filters.get('locations') or [filters.get('location', 'India')]
    keywords = filters.get('keywords', '')

    jobs = []

    for loc in locations:
        page = 1
        limit = 50

        while True:
            params = {
                "page": str(page),
                "limit": str(limit),
                "sortBy": "relevance",
                "descending": "false",
                "internal": "false"
            }
            if loc:
                params['location'] = loc
            if keywords:
                params['keywords'] = keywords

            res = queue_http('https://careers.amd.com/api/jobs', params=params)
            if res.status_code != 200:
                res.raise_for_status()

            data = res.json()
            page_jobs = data.get('jobs', [])
            if not page_jobs:
                break

            for j in page_jobs:
                job = j.get('data', {})
                if not job:
                    continue

                job_id = job.get('req_id') or job.get('slug') or str(int(time.time()))
                loc_val = job.get('full_location') or job.get('short_location') or ", ".join(filter(None, [job.get('city'), job.get('state'), job.get('country')]))
                job_url = job.get('meta_data', {}).get('canonical_url') or job.get('apply_url') or f"https://careers.amd.com/jobs/{job_id}"

                category = (job.get('category') and job['category'][0]) or (job.get('categories') and job['categories'][0]) or ''

                jobs.append({
                    "companyName": company['name'],
                    "jobId": str(job_id),
                    "jobTitle": job.get('title', 'Unknown Title'),
                    "location": loc_val,
                    "department": category,
                    "postedDate": job.get('posted_date') or job.get('create_date') or datetime.utcnow().isoformat() + 'Z',
                    "employmentType": job.get('employment_type', 'Full-time'),
                    "jobDescription": job.get('description', ''),
                    "url": job_url,
                    "applyUrl": job.get('apply_url') or job_url
                })

            if len(page_jobs) < limit:
                break
            page += 1

    return jobs
