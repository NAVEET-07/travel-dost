import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.rfind('01,Cbt ⇆ Rajeev Nagar')
print(f"Found '01,Cbt ⇆ Rajeev Nagar' at index: {idx}")

if idx != -1:
    # Find start of CSV header before this
    header_idx = text.rfind('bus_no,route_name,stops_name_between_route', 0, idx)
    if header_idx != -1:
        snippet = text[header_idx:]
        end_idx = snippet.find('</USER_REQUEST>')
        if end_idx != -1:
            snippet = snippet[:end_idx]
        lines = [l.strip().replace('\\n', '').replace('\\"', '"') for l in snippet.splitlines() if ',' in l and ('→' in l or '⇆' in l or 'bus_no' in l)]
        print(f"Total lines extracted from new user dataset: {len(lines)}")
        print("Header:", lines[0])
        print("First line:", lines[1])
        print("Last line:", lines[-1])
        with open('demo_data/nwkrtc_routes_clean.csv', 'w', encoding='utf-8') as out:
            out.write('\n'.join(lines))
        print("Saved to demo_data/nwkrtc_routes_clean.csv!")
