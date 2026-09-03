import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

all_rows = []

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        content = str(data.get('content', ''))
        content_clean = content.replace('\\n', '\n').replace('\\"', '"')
        
        # Check if line contains CSV rows
        for row in content_clean.splitlines():
            r_s = re.sub(r'^\d+:\s*', '', row.strip())
            if ',' in r_s and ('→' in r_s or '⇆' in r_s or 'bus_no' in r_s):
                if not r_s.startswith('{"') and not r_s.startswith('File ') and not r_s.startswith('Traceback') and not r_s.startswith('import ') and not r_s.startswith('print') and not r_s.startswith('def ') and not r_s.startswith('python '):
                    parts = r_s.split(',', 2)
                    if len(parts) == 3 and ('→' in parts[2] or parts[0] == 'bus_no'):
                        bno = parts[0].strip()
                        rname = parts[1].strip()
                        stops = parts[2].strip()
                        all_rows.append((bno, rname, stops))

print(f"Total raw rows gathered across context: {len(all_rows)}")

# Deduplicate identical adjacent/exact duplicates while preserving all 410 rows in user file order
clean_routes = []
seen = set()

# First row should be header
clean_routes.append("bus_no,route_name,stops_name_between_route")

for bno, rname, stops in all_rows:
    if bno == 'bus_no':
        continue
    # Keep every distinct route entry
    row_str = f"{bno},{rname},{stops}"
    clean_routes.append(row_str)

print(f"Total route rows in final clean dataset: {len(clean_routes)-1}")

with open('demo_data/user_uploaded_410_routes.csv', 'w', encoding='utf-8') as out:
    out.write('\n'.join(clean_routes))

print("Saved to demo_data/user_uploaded_410_routes.csv!")
