import os
import re

base_dir = r"c:\Users\saura\Desktop\Antigravity\Agent1\backend\nlp_service"
scraper_path = os.path.join(base_dir, "scraper.py")

with open(scraper_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

adapter_start = 0
orchestrator_start = 0

for i, line in enumerate(lines):
    if line.strip() == "# --- Adapters ---":
        adapter_start = i
    if line.strip() == "# --- Main orchestrator ---":
        orchestrator_start = i

utils_lines = lines[:adapter_start]
adapter_lines = lines[adapter_start + 1:orchestrator_start]
orchestrator_lines = lines[orchestrator_start:]

# 1. Write utils.py
utils_path = os.path.join(base_dir, "utils.py")
with open(utils_path, "w", encoding="utf-8") as f:
    f.writelines(utils_lines)

# 2. Extract and write adapters
adapters_dir = os.path.join(base_dir, "adapters")
os.makedirs(adapters_dir, exist_ok=True)
with open(os.path.join(adapters_dir, "__init__.py"), "w", encoding="utf-8") as f:
    pass

adapter_text = "".join(adapter_lines)
# Split by 'def scrape_' or 'def get_'
blocks = re.split(r'\n(?=def )', "\n" + adapter_text.strip())

cisco_blocks = []

for block in blocks:
    block = block.strip()
    if not block:
        continue
    match = re.match(r'def ([a-zA-Z0-9_]+)\(', block)
    if not match:
        continue
    func_name = match.group(1)
    
    # special case for cisco
    if 'cisco' in func_name:
        cisco_blocks.append(block)
        continue
        
    adapter_name = func_name.replace("scrape_", "")
    
    file_path = os.path.join(adapters_dir, f"{adapter_name}.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("import time\nimport json\nimport re\nimport base64\nfrom datetime import datetime\n")
        f.write("from utils import queue_http, HEADERS\n\n")
        f.write(block + "\n")

# Write cisco.py
if cisco_blocks:
    cisco_path = os.path.join(adapters_dir, "cisco.py")
    with open(cisco_path, "w", encoding="utf-8") as f:
        f.write("import time\nimport json\nimport re\nimport base64\nfrom datetime import datetime\n")
        f.write("from utils import queue_http, HEADERS\n\n")
        f.write("\n\n".join(cisco_blocks) + "\n")

# 3. Rewrite scraper.py
# It will import utils and all adapters
new_scraper = []
new_scraper.append("import os\nimport time\nimport json\nimport sqlite3\nfrom datetime import datetime\n")
new_scraper.append("from utils import get_db_path, load_settings, extract_skills, extract_yoe, is_allowed, get_crawl_delay_ms\n")
new_scraper.append("from logger import log_scrape_info, log_scrape_error, log_nlp_event\n\n")

new_scraper.append("# Import adapters\n")
new_scraper.append("from adapters.workday import scrape_workday\n")
new_scraper.append("from adapters.smartrecruiters import scrape_smartrecruiters\n")
new_scraper.append("from adapters.cisco import scrape_cisco\n")
new_scraper.append("from adapters.eightfold import scrape_eightfold\n")
new_scraper.append("from adapters.amd import scrape_amd\n")
new_scraper.append("from adapters.ibm import scrape_ibm\n")
new_scraper.append("from adapters.arm import scrape_arm\n\n")

new_scraper.extend(orchestrator_lines)

with open(scraper_path, "w", encoding="utf-8") as f:
    f.writelines(new_scraper)

print("Refactoring complete.")
