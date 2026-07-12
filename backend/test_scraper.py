import json
from nlp_service.adapters.workday import scrape_workday
from nlp_service.adapters.greenhouse import scrape_greenhouse

with open('companies_config.json', 'r') as f:
    config = json.load(f)

for c in config:
    if c['name'] == 'Samsung Research':
        print(f"Scraping {c['name']} (Workday)...")
        # Add the hardcoded variables that utils.py COMPANY_CONFIGS would normally add
        c['workdaySubdomain'] = 'sec.wd3'
        c['workdayTenant'] = 'sec'
        c['workdaySite'] = 'Samsung_Careers'
        jobs = scrape_workday(c, c.get('filters', {}))
        print(f"Found {len(jobs)} jobs for {c['name']}")
        if jobs:
            print("First job title:", jobs[0]['jobTitle'])
            
    if c['name'] == 'Graphcore':
        print(f"Scraping {c['name']} (Greenhouse)...")
        # Add the hardcoded variables
        c['board_token'] = 'graphcore'
        jobs = scrape_greenhouse(c, c.get('filters', {}))
        print(f"Found {len(jobs)} jobs for {c['name']}")
        if jobs:
            print("First job title:", jobs[0]['jobTitle'])
