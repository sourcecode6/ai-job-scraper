import os
import json
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'logs'))

def ensure_logs_dir():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR, exist_ok=True)

def write_log(filename, log_data):
    ensure_logs_dir()
    filepath = os.path.join(LOGS_DIR, filename)
    
    # Ensure timestamp is the first key in the dictionary serialization order
    ordered_log = {}
    ordered_log['timestamp'] = log_data.get('timestamp') or (datetime.utcnow().isoformat() + 'Z')
    
    for k, v in log_data.items():
        if k != 'timestamp':
            ordered_log[k] = v
            
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(ordered_log) + '\n')
    except Exception as e:
        print(f"[Logger Error] Failed to write to log file {filename}: {e}")

def log_scrape_info(message, extra=None):
    data = {"level": "info", "message": message}
    if extra:
        data.update(extra)
    write_log('scrape.log', data)
    print(f"[INFO] {message}")

def log_scrape_error(message, status=None, extra=None):
    data = {"level": "error", "message": message}
    if status is not None:
        data["status"] = status
    if extra:
        data.update(extra)
    # Errors are logged to both scrape.log and error.log
    write_log('scrape.log', data)
    write_log('error.log', data)
    print(f"[ERROR] {message}")

def log_nlp_event(message, event, extra=None):
    data = {
        "level": "info",
        "logType": "nlp",
        "event": event,
        "message": message
    }
    if extra:
        data.update(extra)
    write_log('nlp.log', data)
    write_log('scrape.log', data)
    print(f"[NLP] {event}: {message}")
