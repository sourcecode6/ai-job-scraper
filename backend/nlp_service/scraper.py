import os
import re
import json
import time
import sqlite3
import base64
import urllib.robotparser
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from logger import log_scrape_info, log_scrape_error, log_nlp_event


# Global user agent
USER_AGENT = 'AIJobScraperBot/1.0 (Personal use job tracker; not for commercial use)'
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Robots.txt cache
ROBOTS_CACHE = {}

def get_db_path():
    # Return absolute path to jobs.db
    # In production, app.py runs in backend/nlp_service/
    # jobs.db is in backend/data/jobs.db
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, '..', 'data', 'jobs.db'))

def load_settings():
    settings = {
        'matchThreshold': 65.0,
        'dataRetentionDays': 3,
        'scrapeIntervalHours': 6,
        'globalRequestDelayMs': 3000,
        'betweenCompaniesDelayMs': 10000,
        'crawlDelayDefaultMs': 5000,
    }
    # Read backend/.env
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.abspath(os.path.join(current_dir, '..', '.env'))
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip()
                            if key == 'MATCH_THRESHOLD':
                                settings['matchThreshold'] = float(val)
                            elif key == 'DATA_RETENTION_DAYS':
                                settings['dataRetentionDays'] = int(val)
                            elif key == 'SCRAPE_INTERVAL_HOURS':
                                settings['scrapeIntervalHours'] = int(val)
        except Exception as e:
            print(f"Error loading .env: {e}")
    return settings

# Load skills vocab
def load_skills_vocab():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    vocab_path = os.path.abspath(os.path.join(current_dir, '..', 'data', 'skills_vocab.json'))
    try:
        with open(vocab_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: skills_vocab.json not found: {e}")
        return {"skills": [], "aliases": {}}

VOCAB = load_skills_vocab()
ALL_SKILLS = VOCAB.get('skills', [])
ALIASES = VOCAB.get('aliases', {})

# Build flat lists for extraction
SKILL_LOWER_MAP = {s.lower(): s for s in ALL_SKILLS}
ALIAS_LOWER_MAP = {alias.lower(): canonical for alias, canonical in ALIASES.items()}

def escape_regex(term):
    return re.escape(term)

def build_regex(term):
    escaped = escape_regex(term)
    # Match boundaries for word vs non-word chars
    start = '(?<![a-zA-Z0-9_])' if re.match(r'^[a-zA-Z0-9_]', term) else ''
    end = '(?![a-zA-Z0-9_])' if re.search(r'[a-zA-Z0-9_]$', term) else ''
    return re.compile(start + escaped + end, re.IGNORECASE)

def extract_skills(text):
    if not text:
        return []
    lower = text.lower()
    found = set()

    for lower_skill, canonical in SKILL_LOWER_MAP.items():
        regex = build_regex(lower_skill)
        if regex.search(lower):
            found.add(canonical)

    for alias, canonical in ALIAS_LOWER_MAP.items():
        regex = build_regex(alias)
        if regex.search(lower):
            found.add(canonical)

    return list(found)

def extract_yoe(text):
    if not text:
        return None
    pattern = r'(?:minimum\s+(?:of\s+)?|min\s+)?(\d+)(?:\s*(?:-|to)\s*(\d+))?\s*\+?\s*years?'
    matches = []
    for match in re.finditer(pattern, text, re.IGNORECASE):
        min_val = int(match.group(1))
        start_idx = max(0, match.start() - 60)
        end_idx = min(len(text), match.end() + 40)
        context = text[start_idx:end_idx].lower()
        is_overall = any(w in context for w in ['total', 'overall', 'minimum', 'min', 'at least'])
        matches.append({'minVal': min_val, 'isOverall': is_overall})

    if not matches:
        return None

    overall_match = next((m for m in matches if m['isOverall']), None)
    if overall_match:
        return overall_match['minVal']

    reasonable_matches = [m for m in matches if m['minVal'] <= 15]
    if reasonable_matches:
        return reasonable_matches[0]['minVal']

    return None

# Robots.txt helpers
class RobotsTxtParser:
    def __init__(self, content):
        self.rules = {}
        self.crawl_delays = {}
        self.parse(content)

    def parse(self, content):
        current_agents = []
        for line in content.splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            key = parts[0].strip().lower()
            val = parts[1].strip()
            if key == 'user-agent':
                agent = val.lower()
                current_agents.append(agent)
                if agent not in self.rules:
                    self.rules[agent] = []
            elif key in ('allow', 'disallow'):
                for agent in current_agents:
                    self.rules[agent].append((key == 'allow', val))
            elif key == 'crawl-delay':
                try:
                    delay = float(val)
                    for agent in current_agents:
                        self.crawl_delays[agent] = delay
                except ValueError:
                    pass

    def is_allowed(self, user_agent, url):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        if not path:
            path = '/'
        if parsed.query:
            path += '?' + parsed.query
        
        user_agent = user_agent.lower()
        agent_to_use = next((a for a in self.rules if a != '*' and a in user_agent), '*' if '*' in self.rules else None)
        if not agent_to_use:
            return True

        matching_rules = []
        for is_allow, pattern in self.rules[agent_to_use]:
            regex_parts = []
            for char in pattern:
                if char == '*':
                    regex_parts.append('.*')
                elif char == '$':
                    regex_parts.append('$')
                else:
                    regex_parts.append(re.escape(char))
            regex_str = '^' + ''.join(regex_parts)
            if not pattern.endswith('$'):
                regex_str += '.*'
            if re.match(regex_str, path):
                matching_rules.append((is_allow, pattern))

        if not matching_rules:
            return True

        matching_rules.sort(key=lambda x: (len(x[1]), x[0]), reverse=True)
        return matching_rules[0][0]

    def get_crawl_delay(self, user_agent):
        user_agent = user_agent.lower()
        for agent in self.crawl_delays:
            if agent != '*' and agent in user_agent:
                return self.crawl_delays[agent]
        return self.crawl_delays.get('*')

def fetch_robots(career_url):
    try:
        parsed_url = urllib.parse.urlparse(career_url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

        if robots_url in ROBOTS_CACHE:
            return ROBOTS_CACHE[robots_url]

        req = urllib.request.Request(robots_url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read().decode('utf-8', errors='ignore')
        
        parser = RobotsTxtParser(content)
        ROBOTS_CACHE[robots_url] = parser
        return parser
    except Exception:
        return None

def is_allowed(target_url):
    rp = fetch_robots(target_url)
    if not rp:
        return True
    return rp.is_allowed(USER_AGENT, target_url)

def get_crawl_delay_ms(career_url, default_delay):
    rp = fetch_robots(career_url)
    if not rp:
        return default_delay
    delay = rp.get_crawl_delay(USER_AGENT)
    if delay is not None:
        return int(delay * 1000)
    return default_delay
    return default_delay

COMPANY_CONFIGS = {
    'NVIDIA': {
        'workdayTenant': 'nvidia',
        'workdaySite': 'NVIDIAExternalCareerSite',
        'workdaySubdomain': 'nvidia.wd5',
    },
    'Arista Networks': {
        'smartRecruitersId': 'AristaNetworks',
    },
    'Qualcomm': {
        'eightfoldBaseUrl': 'https://careers.qualcomm.com',
        'eightfoldDomain': 'qualcomm.com',
    },
    'Broadcom': {
        'workdayTenant': 'broadcom',
        'workdaySite': 'External_Career',
        'workdaySubdomain': 'broadcom.wd1',
    },
    'Intel': {
        'workdayTenant': 'intel',
        'workdaySite': 'External',
        'workdaySubdomain': 'intel.wd1',
    },
    'Microsoft': {
        'eightfoldBaseUrl': 'https://apply.careers.microsoft.com',
        'eightfoldDomain': 'microsoft.com',
    },
    'Ericsson': {
        'eightfoldBaseUrl': 'https://jobs.ericsson.com',
        'eightfoldDomain': 'ericsson.com',
    }
}

# Custom HTTP rate-limited queue simulation
GLOBAL_LAST_REQUEST_TIME = 0.0

def queue_http(url, method='GET', **kwargs):
    global GLOBAL_LAST_REQUEST_TIME
    settings = load_settings()
    delay_sec = settings['globalRequestDelayMs'] / 1000.0

    # Enforce global rate-limit gap
    elapsed = time.time() - GLOBAL_LAST_REQUEST_TIME
    if elapsed < delay_sec:
        time.sleep(delay_sec - elapsed)

    kwargs.setdefault('headers', HEADERS)
    kwargs.setdefault('timeout', 15)

    try:
        if method.upper() == 'POST':
            response = requests.post(url, **kwargs)
        else:
            response = requests.get(url, **kwargs)
        GLOBAL_LAST_REQUEST_TIME = time.time()
        return response
    except Exception as e:
        GLOBAL_LAST_REQUEST_TIME = time.time()
        raise e

# --- Adapters ---

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
            job_url = f"{base_url}{ext_path}" if ext_path else company['careerUrl']

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

def scrape_smartrecruiters(company, filters):
    # Works for Arista Networks
    company_id = company['smartRecruitersId']
    endpoint = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"

    jobs = []
    offset = 0
    limit = 100
    has_more = True

    while has_more:
        params = {"limit": limit, "offset": offset}
        if filters.get('country'):
            params['country'] = filters['country']

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

def get_cisco_csrf():
    res = queue_http('https://careers.cisco.com/global/en/search-results')
    if res.status_code != 200:
        res.raise_for_status()

    cookies = res.cookies
    cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])

    play_session = cookies.get('PLAY_SESSION')
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
    location = filters.get('location', 'India')
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
                "country": [location]
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

def scrape_eightfold(company, filters):
    # Works for Qualcomm, Microsoft, Ericsson
    base_url = company['eightfoldBaseUrl']
    domain = company['eightfoldDomain']
    search_url = f"{base_url}/api/pcsx/search"

    jobs = []
    start = 0
    page_size = 10
    total = None

    while True:
        params = {
            "domain": domain,
            "location": filters.get('location', 'India'),
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
            loc = ", ".join(p.get('locations', []))
            job_url = f"{base_url}{p.get('positionUrl', '/careers')}"

            jobs.append({
                "companyName": company['name'],
                "jobId": str(job_id),
                "jobTitle": p.get('name', 'Unknown Title'),
                "location": loc,
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

def scrape_amd(company, filters):
    # Works for AMD
    location = filters.get('location', 'India')
    keywords = filters.get('keywords', '')

    jobs = []
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
        if location:
            params['location'] = location
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
            loc = job.get('full_location') or job.get('short_location') or ", ".join(filter(None, [job.get('city'), job.get('state'), job.get('country')]))
            job_url = job.get('meta_data', {}).get('canonical_url') or job.get('apply_url') or f"https://careers.amd.com/jobs/{job_id}"

            category = (job.get('category') and job['category'][0]) or (job.get('categories') and job['categories'][0]) or ''

            jobs.append({
                "companyName": company['name'],
                "jobId": str(job_id),
                "jobTitle": job.get('title', 'Unknown Title'),
                "location": loc,
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

def scrape_ibm(company, filters):
    # Works for IBM
    endpoint = 'https://www-api.ibm.com/search/api/v2'

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

        if filters.get('country'):
            body['query']['bool']['must'].append({"match": {"field_keyword_05": filters['country']}})
        if filters.get('category'):
            body['query']['bool']['must'].append({"match": {"field_keyword_08": filters['category']}})

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
                "url": src.get('url') or company['careerUrl'],
                "applyUrl": src.get('url') or company['careerUrl']
            })

        from_offset += len(hits)
        if from_offset >= total or len(hits) < page_size:
            break

    return jobs

# --- Main orchestrator ---

def parse_relative_date(date_str, retention_days):
    now = datetime.utcnow()
    expires_at = now + timedelta(days=retention_days)

    if not date_str:
        return now.isoformat() + 'Z', expires_at.isoformat() + 'Z'

    # Try ISO or standard datetime parse
    try:
        # standard ISO parsing
        # Remove trailing Z if present for python < 3.11 compatibility
        s = date_str.rstrip('Z')
        parsed = datetime.fromisoformat(s)
        return date_str, (parsed + timedelta(days=retention_days)).isoformat() + 'Z'
    except ValueError:
        pass

    # Handle relative date strings
    lower = date_str.lower()
    days_ago = 0
    if 'yesterday' in lower:
        days_ago = 1
    elif 'today' in lower:
        days_ago = 0
    else:
        days_match = re.search(r'(\d+)\s+days?\s+ago', lower)
        if days_match:
            days_ago = int(days_match.group(1))
        else:
            weeks_match = re.search(r'(\d+)\s+weeks?\s+ago', lower)
            if weeks_match:
                days_ago = int(weeks_match.group(1)) * 7
            elif 'month' in lower or 'year' in lower or '30+ days' in lower:
                days_ago = 30

    if days_ago > 0:
        posted_date = now - timedelta(days=days_ago)
        expires_at = now - timedelta(days=days_ago - retention_days)
        return posted_date.isoformat() + 'Z', expires_at.isoformat() + 'Z'

    return now.isoformat() + 'Z', expires_at.isoformat() + 'Z'

def scrape_company(company_row, model):
    start_time = time.time()
    company = dict(company_row)
    name = company['name']
    if name in COMPANY_CONFIGS:
        company.update(COMPANY_CONFIGS[name])

    ats = company['ats']
    tier = company['tier']
    career_url = company['career_url']
    filters = json.loads(company['filters'] or '{}')

    if name == 'Arista Networks':
        allow_bypass = os.environ.get('ALLOW_ARISTA_BYPASS', 'false').lower() in ('true', '1', 'yes')
        if not allow_bypass:
            log_scrape_info(f"[{name}] Blocked by robots.txt — skipping (ALLOW_ARISTA_BYPASS is false)")
            return

    log_scrape_info(f"[{name}] Starting acquisition (ats={ats}, tier={tier})")

    # Determine the target endpoint URL to check against robots.txt
    target_url = career_url
    if ats == 'eightfold':
        target_url = f"{company['eightfoldBaseUrl']}/api/pcsx/search"
    elif ats == 'smartrecruiters':
        target_url = f"https://api.smartrecruiters.com/v1/companies/{company['smartRecruitersId']}/postings"
    elif ats == 'cisco':
        target_url = "https://careers.cisco.com/widgets"
    elif ats == 'amd':
        target_url = "https://careers.amd.com/api/jobs"
    elif ats == 'ibm':
        target_url = "https://www-api.ibm.com/search/api/v2"

    # Check robots.txt compliance
    if tier >= 2 and ats != 'workday':
        is_arista = (name == 'Arista Networks')
        allow_bypass = os.environ.get('ALLOW_ARISTA_BYPASS', 'false').lower() in ('true', '1', 'yes')
        
        if not (is_arista and allow_bypass):
            if not is_allowed(target_url):
                log_scrape_error(f"[{name}] Blocked by robots.txt — skipping (target_url={target_url})")
                return

    try:
        raw_jobs = []
        if ats == 'workday':
            raw_jobs = scrape_workday(company, filters)
        elif ats == 'smartrecruiters':
            raw_jobs = scrape_smartrecruiters(company, filters)
        elif ats == 'cisco':
            raw_jobs = scrape_cisco(company, filters)
        elif ats == 'eightfold':
            raw_jobs = scrape_eightfold(company, filters)
        elif ats == 'amd':
            raw_jobs = scrape_amd(company, filters)
        elif ats == 'ibm':
            raw_jobs = scrape_ibm(company, filters)
        else:
            # Fallback (Google is commented out, so we don't expect other types)
            log_scrape_error(f"[{name}] ATS type {ats} not fully implemented in python. Skipping.")
            return

        new_count = 0
        skip_count = 0
        settings = load_settings()
        retention = settings['dataRetentionDays']

        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()

        for job in raw_jobs:
            # Check duplicate
            cursor.execute("SELECT 1 FROM jobs WHERE company_name = ? AND job_id = ?", (name, job['jobId']))
            if cursor.fetchone():
                skip_count += 1
                continue

            posted_date_str, expires_at_str = parse_relative_date(job['postedDate'], retention)
            skills = extract_skills(f"{job['jobTitle']} {job['department']} {job['jobDescription']}")
            yoe = extract_yoe(job['jobDescription'])

            # Generate embeddings immediately if model is provided
            title_vec_str = None
            desc_vec_str = None
            status = 'pending'

            if model:
                try:
                    # Title Embedding
                    title_vector = model.encode([job['jobTitle']])[0].tolist()
                    title_vec_str = json.dumps(title_vector)

                    # Description/Combined Embedding (with chunking)
                    desc_text = f"{job['jobTitle']} {job['department']} {job['jobDescription']}"
                    chunk_size = 2000
                    overlap = 200
                    chunks = []
                    i = 0
                    while i < len(desc_text):
                        chunk = desc_text[i:i + chunk_size].strip()
                        if chunk:
                            chunks.append(chunk)
                        if i + chunk_size >= len(desc_text):
                            break
                        i += (chunk_size - overlap)

                    if chunks:
                        chunk_embeddings = model.encode(chunks)
                        import numpy as np
                        avg_embedding = np.mean(chunk_embeddings, axis=0)
                        norm = np.linalg.norm(avg_embedding)
                        if norm > 0:
                            avg_embedding = avg_embedding / norm
                        desc_vec_str = json.dumps(avg_embedding.tolist())
                        status = 'done'
                        log_nlp_event(
                            message="Job embeddings stored",
                            event="job_embedding",
                            extra={
                                "company": name,
                                "jobId": job['jobId'],
                                "titleVectorDimensions": 384,
                                "descVectorDimensions": 384
                            }
                        )
                except Exception as embed_err:
                    log_scrape_error(f"[{name}] Embedding generation failed for job {job['jobId']}: {embed_err}")
                    status = 'failed'

            cursor.execute("""
                INSERT INTO jobs (
                    company_name, job_id, job_title, location, department,
                    posted_date, employment_type, job_description, url, apply_url,
                    skills_display, required_yoe, embedding_status, scraped_at, expires_at,
                    title_vector, description_vector, embedding_vector
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, job['jobId'], job['jobTitle'], job['location'], job['department'],
                posted_date_str, job['employmentType'], job['jobDescription'], job['url'], job['applyUrl'],
                json.dumps(skills), yoe, status, datetime.utcnow().isoformat() + 'Z', expires_at_str,
                title_vec_str, desc_vec_str, desc_vec_str
            ))
            new_count += 1

        # Update last_scraped_at
        cursor.execute("UPDATE companies SET last_scraped_at = ?, status = 'active', degraded_reason = NULL WHERE name = ?", 
                       (datetime.utcnow().isoformat() + 'Z', name))
        conn.commit()
        conn.close()

        # Log completion log structure
        log_entry = {
            "company": name,
            "status": "success",
            "jobsFound": len(raw_jobs),
            "jobsNew": new_count,
            "jobsSkipped": skip_count,
            "durationMs": int((time.time() - start_time) * 1000)
        }
        log_scrape_info(f"[{name}] Scraping success", log_entry)

    except Exception as e:
        log_scrape_error(f"[{name}] Acquisition error: {e}")
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        # Mark degraded
        cursor.execute("UPDATE companies SET status = 'degraded', degraded_reason = ? WHERE name = ?", (str(e), name))
        conn.commit()
        conn.close()


def run_acquisition_cycle(model):
    print("=== Python Acquisition cycle started ===")
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}. Waiting for schema initialization.")
        return

    conn = sqlite3.connect(db_path, timeout=30.0)
    # Return dictionary rows
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM companies WHERE status = 'active'")
    companies = cursor.fetchall()
    conn.close()

    settings = load_settings()
    between_delay = settings['betweenCompaniesDelayMs'] / 1000.0

    for i, company in enumerate(companies):
        if i > 0:
            print(f"Waiting {between_delay}s before next company...")
            time.sleep(between_delay)
        try:
            scrape_company(company, model)
        except Exception as e:
            print(f"Fatal error scraping company {company['name']}: {e}")

    print("=== Python Acquisition cycle complete ===")

def run_cleanup():
    print("=== Python daily cleanup started ===")
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM jobs WHERE expires_at < datetime('now')")
        jobs_deleted = cursor.rowcount
        
        cursor.execute("DELETE FROM matched_jobs WHERE expires_at < datetime('now')")
        matched_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        print(f"Python daily cleanup complete: {jobs_deleted} jobs deleted, {matched_deleted} matched_jobs deleted")
    except Exception as e:
        print(f"Error in python daily cleanup: {e}")

