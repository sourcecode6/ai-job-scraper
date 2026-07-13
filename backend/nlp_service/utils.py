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
        'matchThreshold': float(os.environ.get('MATCH_THRESHOLD', 65.0)),
        'dataRetentionDays': int(os.environ.get('DATA_RETENTION_DAYS', 3)),
        'scrapeIntervalHours': int(os.environ.get('SCRAPE_INTERVAL_HOURS', 6)),
        'globalRequestDelayMs': 3000,
        'betweenCompaniesDelayMs': 10000,
        'crawlDelayDefaultMs': 5000,
    }
    # Read backend/.env as fallback/override
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
    },
    'Cloudflare': {
        'board_token': 'cloudflare',
    },
    'Cerebras Systems': {
        'board_token': 'cerebras',
    },
    'NetApp': {
        'eightfoldBaseUrl': 'https://netapp.eightfold.ai',
        'eightfoldDomain': 'netapp.com',
    },
    'Hewlett Packard Enterprise': {
        'workdayTenant': 'hpe',
        'workdaySite': 'Jobsathpe',
        'workdaySubdomain': 'hpe.wd5',
    },
    'Juniper Networks': {
        'workdayTenant': 'hpe',
        'workdaySite': 'Jobsathpe',
        'workdaySubdomain': 'hpe.wd5',
    },
    'NXP Semiconductors': {
        'workdayTenant': 'nxp',
        'workdaySite': 'Careers',
        'workdaySubdomain': 'nxp.wd3',
    },
    'Samsung Research': {
        'workdayTenant': 'sec',
        'workdaySite': 'Samsung_Careers',
        'workdaySubdomain': 'sec.wd3',
    },
    'Graphcore': {
        'board_token': 'graphcore',
    }
}

# Custom HTTP rate-limited queue simulation
GLOBAL_LAST_REQUEST_TIME = 0.0

def queue_http(url, method='GET', max_retries=3, **kwargs):
    global GLOBAL_LAST_REQUEST_TIME
    settings = load_settings()
    delay_sec = settings['globalRequestDelayMs'] / 1000.0

    kwargs.setdefault('headers', HEADERS)
    kwargs.setdefault('timeout', 15)
    
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        # Enforce global rate-limit gap
        elapsed = time.time() - GLOBAL_LAST_REQUEST_TIME
        if elapsed < delay_sec:
            time.sleep(delay_sec - elapsed)
            
        try:
            if method.upper() == 'POST':
                response = requests.post(url, **kwargs)
            else:
                response = requests.get(url, **kwargs)
                
            GLOBAL_LAST_REQUEST_TIME = time.time()
            
            if response.status_code == 429:
                log_scrape_info(f"Rate limited (429) on {url}. Retrying... ({attempt}/{max_retries})")
                time.sleep(delay_sec * attempt * 2) # Exponential backoff
                continue
                
            return response
            
        except requests.exceptions.RequestException as e:
            GLOBAL_LAST_REQUEST_TIME = time.time()
            if attempt < max_retries:
                log_scrape_info(f"Network error on {url}: {e}. Retrying... ({attempt}/{max_retries})")
                time.sleep(delay_sec * attempt)
                continue
            raise e
            
    raise Exception(f"Max retries ({max_retries}) exceeded for {url}")

