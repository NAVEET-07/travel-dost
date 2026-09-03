import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_full_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

lines_dict = {}

with open(transcript_full_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace escaped newlines and quotes
text_clean = text.replace('\\n', '\n').replace('\\"', '"')

for raw_line in text_clean.splitlines():
    clean = raw_line.strip()
    # Strip line numbers like "128: " or "128: "
    clean = re.sub(r'^\d+:\s*', '', clean)
    if clean.startswith('bus_no,') or (',' in clean and ('→' in clean or '⇆' in clean)):
        if 'stops_name_between_route' in clean or clean.count(',') >= 2:
            parts = clean.split(',', 2)
            if len(parts) == 3:
                bus_no = parts[0].strip()
                route_name = parts[1].strip()
                stops = parts[2].strip()
                key = (bus_no, route_name, stops)
                lines_dict[key] = f"{bus_no},{route_name},{stops}"

all_routes = list(lines_dict.values())
print(f"Total unique clean bus routes extracted: {len(all_routes)}")

# Ensure header is first
header = "bus_no,route_name,stops_name_between_route"
final_routes = [header] + [r for r in all_routes if not r.startswith("bus_no,")]

print(f"Final total routes (including header): {len(final_routes)}")

with open('demo_data/nwkrtc_routes.csv', 'w', encoding='utf-8') as out:
    out.write('\n'.join(final_routes))

print("Successfully wrote demo_data/nwkrtc_routes.csv!")
