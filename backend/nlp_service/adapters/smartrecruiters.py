import time
import json
import re
import base64
from datetime import datetime
from backend.nlp_service.utils import queue_http, HEADERS

def scrape_smartrecruiters(company, filters):
    # Works for Arista Networks
    company_id = company['smartRecruitersId']
    endpoint = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"

    countries = filters.get('countries') or ([filters.get('country')] if filters.get('country') else [None])
    jobs = []

    for country in countries:
        offset = 0
        limit = 100
        has_more = True

        while has_more:
            params = {"limit": limit, "offset": offset}
            if country:
                params['country'] = country

            res = queue_http(endpoint, params=params)
            if res.status_code != 200:
                res.raise_for_status()

            data = res.json()
            postings = data.get('content', [])
            if not postings:
                break

            for p in postings:
                job_id = p.get('refNumber') or p.get('id') or str(int(time.time()))
                location_parts = [p.get('location', {}).get('city'), p.get('location', {}).get('region'), p.get('location', {}).get('country')]
                location = ", ".join(filter(None, location_parts))
                job_url = f"https://jobs.smartrecruiters.com/{company_id}/{p.get('id')}"

                jobs.append({
                    "companyName": company['name'],
                    "jobId": str(job_id),
                    "jobTitle": p.get('name', 'Unknown Title'),
                    "location": location,
                    "department": p.get('department', {}).get('label', ''),
                    "postedDate": p.get('releasedDate', datetime.utcnow().isoformat() + 'Z'),
                    "employmentType": p.get('typeOfEmployment', {}).get('label', 'Full-time'),
                    "jobDescription": p.get('customField', {}).get('description', ''),
                    "url": job_url,
                    "applyUrl": job_url
                })

            total = data.get('totalFound', 0)
            offset += len(postings)
            if offset >= total or len(postings) < limit:
                has_more = False

    return jobs
