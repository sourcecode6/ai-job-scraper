import os

def get_db_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, '..', 'data', 'jobs.db'))

def load_settings():
    settings = {
        'matchThreshold': float(os.environ.get('MATCH_THRESHOLD', 65.0)),
        'dataRetentionDays': int(os.environ.get('DATA_RETENTION_DAYS', 3)),
        'scrapeIntervalHours': int(os.environ.get('SCRAPE_INTERVAL_HOURS', 6)),
        'maxConcurrentCompanies': int(os.environ.get('MAX_CONCURRENT_COMPANIES', 3)),
        'globalRequestDelayMs': 3000,
        'betweenCompaniesDelayMs': 10000,
        'crawlDelayDefaultMs': 5000,
    }
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
                            if key == 'MATCH_THRESHOLD': settings['matchThreshold'] = float(val)
                            elif key == 'DATA_RETENTION_DAYS': settings['dataRetentionDays'] = int(val)
                            elif key == 'SCRAPE_INTERVAL_HOURS': settings['scrapeIntervalHours'] = int(val)
                            elif key == 'MAX_CONCURRENT_COMPANIES': settings['maxConcurrentCompanies'] = int(val)
        except Exception as e:
            print(f"Error reading .env: {e}")
    return settings
