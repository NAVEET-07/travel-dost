import os
import sys
import json
import re
import csv

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

print(f"Reading transcript from absolute path: {os.path.abspath(transcript_path)}")

all_raw_csv_lines = []

with open(transcript_path, 'r', encoding='utf-8') as f:
    for step_num, line in enumerate(f):
        # Look for prompt context containing bus_no,route_name
        if 'stops_name_between_route' in line:
            data = json.loads(line)
            content = str(data.get('content', ''))
            content_clean = content.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            
            idx = content_clean.find('bus_no,route_name,stops_name_between_route')
            if idx != -1:
                sub = content_clean[idx:]
                end_req = sub.find('</USER_REQUEST>')
                if end_req != -1:
                    sub = sub[:end_req]
                
                rows = [l.strip() for l in sub.splitlines() if ',' in l and ('→' in l or '⇆' in l or 'bus_no' in l)]
                for r in rows:
                    if not any(r.startswith(kw) for kw in ['{"', 'File ', 'Traceback', 'import ', 'print', 'def ', 'target', 'prefix', 'suffix', 'clean_lines']):
                        all_raw_csv_lines.append((step_num, r))

print(f"Found {len(all_raw_csv_lines)} total CSV line occurrences across transcript steps.")

# Deduplicate identical CSV lines while keeping all 564 unique user route rows
unique_csv_rows = []
seen = set()

for step_num, row_str in all_raw_csv_lines:
    if row_str.startswith('bus_no,'):
        continue
    parts = row_str.split(',', 2)
    if len(parts) == 3:
        bno = parts[0].strip()
        rname = parts[1].strip()
        stops = parts[2].strip()
        row_tuple = (bno, rname, stops)
        if row_tuple not in seen:
            seen.add(row_tuple)
            unique_csv_rows.append(f"{bno},{rname},{stops}")

print(f"Total Unique CSV Routes Extracted across user messages: {len(unique_csv_rows)}")

# If count is less than 564, let's check how many total forward + return + branch combinations exist
print("\n--- Inspecting route numbers ---")
bno_set = set(r.split(',')[0] for r in unique_csv_rows)
print(f"Unique bus_no prefixes: {len(bno_set)}")
