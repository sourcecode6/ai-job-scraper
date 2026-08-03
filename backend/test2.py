import json
from backend.nlp_service.adapters.workday import scrape_workday
from backend.nlp_service.adapters.greenhouse import scrape_greenhouse

config = json.load(open('C:/Users/saura/Desktop/Antigravity/Agent1/backend/companies_config.json', 'r'))

for c in config:
    if c['name'] == 'Samsung Research':
        c['workdaySubdomain'] = 'sec.wd3'
        c['workdayTenant'] = 'sec'
        c['workdaySite'] = 'Samsung_Careers'
        jobs = scrape_workday(c, c.get('filters', {}))
        print(f"Found {len(jobs)} jobs for Samsung. First: {jobs[0]['jobTitle'] if jobs else 'None'}")
        
    if c['name'] == 'Graphcore':
        c['board_token'] = 'graphcore'
        jobs = scrape_greenhouse(c, c.get('filters', {}))
        print(f"Found {len(jobs)} jobs for Graphcore. First: {jobs[0]['jobTitle'] if jobs else 'None'}")
