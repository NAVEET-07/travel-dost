import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    full_text = f.read()

# Replace escaped newlines
text_clean = full_text.replace('\\n', '\n').replace('\\"', '"')

routes_dict = {}
for line in text_clean.splitlines():
    l = re.sub(r'^\d+:\s*', '', line.strip())
    if ('→' in l or '⇆' in l) and ',' in l and not l.startswith('File ') and not l.startswith('Traceback') and not l.startswith('import ') and not l.startswith('print('):
        parts = l.split(',', 2)
        if len(parts) == 3:
            bus_no = parts[0].strip()
            route_name = parts[1].strip()
            stops = parts[2].strip()
            if '→' in stops or '⇆' in route_name:
                key = (bus_no, route_name, stops)
                routes_dict[key] = f"{bus_no},{route_name},{stops}"

print(f"Total unique bus routes found across entire transcript: {len(routes_dict)}")

header = "bus_no,route_name,stops_name_between_route"
routes_list = [header] + list(routes_dict.values())

with open('demo_data/nwkrtc_routes_complete.csv', 'w', encoding='utf-8') as out:
    out.write('\n'.join(routes_list))

print("Saved to demo_data/nwkrtc_routes_complete.csv")
