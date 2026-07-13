import time
import json
import re
import base64
from datetime import datetime
from utils import queue_http, HEADERS

def scrape_ibm(company, filters):
    # Works for IBM
    endpoint = 'https://www-api.ibm.com/search/api/v2'

    countries = filters.get('countries') or ([filters.get('country')] if filters.get('country') else [])
    category = filters.get('category')

    jobs = []
    from_offset = 0
    page_size = 50

    while True:
        body = {
            "appId": "careers",
            "scopes": ["careers2"],
            "query": {
                "bool": {
                    "must": []
                }
            },
            "from": from_offset,
            "size": page_size,
            "lang": "zz",
            "_source": [
                "_id", "title", "url", "description", "language",
                "field_keyword_05", "field_keyword_08", "field_keyword_17", "field_keyword_19"
            ]
        }

        if countries:
            body['query']['bool']['must'].append({"terms": {"field_keyword_05": countries}})
        if category:
            body['query']['bool']['must'].append({"match": {"field_keyword_08": category}})

        res = queue_http(endpoint, method='POST', json=body)
        if res.status_code != 200:
            res.raise_for_status()

        data = res.json()
        hits = data.get('hits', {}).get('hits', [])
        total = data.get('hits', {}).get('total', {}).get('value', 0)

        if not hits:
            break

        for hit in hits:
            src = hit.get('_source', {})
            job_id_match = re.search(r'jobId=(\d+)', src.get('url', ''))
            job_id = job_id_match.group(1) if job_id_match else hit.get('_id') or str(int(time.time()))

            loc = src.get('field_keyword_19') or src.get('field_keyword_05') or ''
            work_mode = src.get('field_keyword_17') or 'Full-time'

            jobs.append({
                "companyName": company['name'],
                "jobId": str(job_id),
                "jobTitle": src.get('title', 'Unknown Title'),
                "location": loc,
                "department": src.get('field_keyword_08', ''),
                "postedDate": datetime.utcnow().isoformat() + 'Z',
                "employmentType": work_mode,
                "jobDescription": src.get('description', ''),
                "url": src.get('url') or company['career_url'],
                "applyUrl": src.get('url') or company['career_url']
            })

        from_offset += len(hits)
        if from_offset >= total or len(hits) < page_size:
            break

    return jobs
