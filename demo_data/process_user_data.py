import json
import re

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Match CSV lines in prompt context
pattern = re.compile(r'([A-Z0-9\-]+,\s*[^,\n]+\s*,\s*[^,\n]+→[^\n]+)', re.UNICODE)
matches = pattern.findall(text)

print(f"Extracted {len(matches)} raw route rows")

unique_routes = {}
for m in matches:
    clean_row = m.strip()
    parts = clean_row.split(',', 2)
    if len(parts) == 3:
        bno = parts[0].strip()
        rname = parts[1].strip()
        stops = parts[2].strip()
        if '→' in stops and not bno.startswith('import') and not bno.startswith('def') and len(bno) <= 15:
            key = (bno, rname, stops)
            unique_routes[key] = f"{bno},{rname},{stops}"

print(f"Unique valid routes found: {len(unique_routes)}")

final_csv_lines = ["bus_no,route_name,stops_name_between_route"] + list(unique_routes.values())

with open('demo_data/nwkrtc_routes_clean.csv', 'w', encoding='utf-8') as out:
    out.write('\n'.join(final_csv_lines))

print(f"Wrote {len(final_csv_lines)} lines to demo_data/nwkrtc_routes_clean.csv!")
