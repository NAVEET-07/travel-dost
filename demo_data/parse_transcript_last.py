import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

user_lines = []

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        content = data.get('content', '')
        if isinstance(content, str) and '01,Cbt ⇆ Rajeev Nagar' in content:
            idx = content.find('bus_no,route_name,stops_name_between_route')
            if idx != -1:
                csv_part = content[idx:]
                end_pos = csv_part.find('</USER_REQUEST>')
                if end_pos != -1:
                    csv_part = csv_part[:end_pos]
                
                raw_lines = csv_part.splitlines()
                print(f"Raw lines found: {len(raw_lines)}")
                for r_line in raw_lines:
                    r_clean = r_line.strip()
                    if ',' in r_clean and ('→' in r_clean or '⇆' in r_clean or 'bus_no' in r_clean):
                        user_lines.append(r_clean)
                print(f"Filtered clean CSV lines: {len(user_lines)}")
                break

if user_lines:
    print("Header:", user_lines[0])
    print("Line 1:", user_lines[1])
    print("Line -1:", user_lines[-1])
    with open('demo_data/nwkrtc_routes_clean.csv', 'w', encoding='utf-8') as out:
        out.write('\n'.join(user_lines))
    print("Saved to demo_data/nwkrtc_routes_clean.csv!")
