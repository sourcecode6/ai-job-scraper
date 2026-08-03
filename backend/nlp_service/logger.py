import os
import json
from loguru import logger
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'logs'))

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)

# Configure Loguru to write JSON to separate files using enqueue=True (async)
logger.remove() # Remove default stderr logger

# Define custom JSON formatter
def format_json(record):
    # Reconstruct the log structure the system expects
    payload = record["extra"].get("payload", {})
    
    ordered_log = {}
    ordered_log['timestamp'] = record["time"].isoformat() + 'Z'
    
    # Base fields
    ordered_log['level'] = record["level"].name.lower()
    if "logType" in payload:
        ordered_log['logType'] = payload.pop("logType")
    if "event" in payload:
        ordered_log['event'] = payload.pop("event")
        
    ordered_log['message'] = record["message"]
    
    # Merge any remaining extra payload
    for k, v in payload.items():
        ordered_log[k] = v
        
    # Serialize and store in extra to avoid curly brace format string parsing errors
    record["extra"]["serialized"] = json.dumps(ordered_log)
    return "{extra[serialized]}\n"


# Scrape.log gets INFO and ERROR for scraper
logger.add(os.path.join(LOGS_DIR, 'scrape.log'), 
           filter=lambda record: record["extra"].get("dest") in ["scrape", "all"],
           format=format_json, 
           enqueue=True, 
           rotation="10 MB")

# Error.log gets only ERROR
logger.add(os.path.join(LOGS_DIR, 'error.log'), 
           filter=lambda record: record["extra"].get("dest") in ["error", "all"] and record["level"].name == "ERROR",
           format=format_json, 
           enqueue=True, 
           rotation="10 MB")

# NLP.log gets NLP specific logs
logger.add(os.path.join(LOGS_DIR, 'nlp.log'), 
           filter=lambda record: record["extra"].get("dest") in ["nlp", "all"],
           format=format_json, 
           enqueue=True, 
           rotation="10 MB")

# Re-add console logger for debugging in terminal
logger.add(lambda msg: print(msg, end=""), format="[{level}] {message}")


def log_scrape_info(message, extra=None):
    payload = extra or {}
    logger.bind(dest="scrape", payload=payload).info(message)

def log_scrape_error(message, status=None, extra=None):
    payload = extra or {}
    if status is not None:
        payload["status"] = status
    # Dest 'all' routes to scrape.log and error.log (due to error filter)
    logger.bind(dest="all", payload=payload).error(message)

def log_nlp_event(message, event, extra=None):
    payload = extra or {}
    payload["logType"] = "nlp"
    payload["event"] = event
    # Dest 'all' routes to nlp.log and scrape.log
    logger.bind(dest="all", payload=payload).info(message)
