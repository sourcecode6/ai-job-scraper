import time
import json
import re
import base64
from datetime import datetime
from utils import queue_http, HEADERS

def scrape_workday(company, filters):
    # Works for NVIDIA, Broadcom, Intel
    subdomain = company['workdaySubdomain']
    tenant = company['workdayTenant']
    site = company['workdaySite']
    endpoint = f"https://{subdomain}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"

    jobs = []
    offset = 0
    limit = filters.get('limit', 20)
    has_more = True

    while has_more:
        body = {
            "limit": limit,
            "offset": offset,
            "searchText": filters.get('searchText', ''),
            "locations": filters.get('locations', [])
        }
        res = queue_http(endpoint, method='POST', json=body)
        if res.status_code != 200:
            res.raise_for_status()

        data = res.json()
        postings = data.get('jobPostings', [])
        if not postings:
            break

        for p in postings:
            ext_path = p.get('externalPath', '')
            if ext_path.startswith('/job/'):
                ext_path = f"/en-US/{site}{ext_path}"
            base_url = f"https://{subdomain}.myworkdayjobs.com"
            job_url = f"{base_url}{ext_path}" if ext_path else company['career_url']

            jobs.append({
                "companyName": company['name'],
                "jobId": p.get('bulletFields', [None])[0] or (p.get('title', '').replace(' ', '-').lower() + '-' + str(int(time.time()))),
                "jobTitle": p.get('title', 'Unknown Title'),
                "location": p.get('locationsText', ''),
                "department": p.get('jobCategories', [{}])[0].get('value', '') if p.get('jobCategories') else '',
                "postedDate": p.get('postedOn', datetime.utcnow().isoformat() + 'Z'),
                "employmentType": p.get('timeType', 'Full-time'),
                "jobDescription": p.get('jobDescription', '').strip(),
                "url": job_url,
                "applyUrl": job_url
            })

        total = data.get('total', 0)
        offset += len(postings)
        if offset >= total or len(postings) < limit:
            has_more = False

    return jobs
