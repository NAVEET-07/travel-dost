import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for step_num, line in enumerate(f):
        if '01,Cbt ⇆ Rajeev Nagar' in line and 'import ' not in line and 'def ' not in line:
            print(f"Match found in step {step_num}!")
            # Find start of dataset
            idx = line.find('01,Cbt ⇆ Rajeev Nagar')
            # find header before it if present
            h_idx = line.rfind('bus_no,route_name', 0, idx)
            if h_idx == -1:
                h_idx = idx
            
            sub = line[h_idx:]
            end_p = sub.find('</USER_REQUEST>')
            if end_p != -1:
                sub = sub[:end_p]
            
            sub_clean = sub.replace('\\n', '\n').replace('\\"', '"')
            rows = []
            for r in sub_clean.splitlines():
                r_s = re.sub(r'^\d+:\s*', '', r.strip())
                if ',' in r_s and ('→' in r_s or '⇆' in r_s or 'bus_no' in r_s):
                    if not r_s.startswith('{"') and not r_s.startswith('File ') and not r_s.startswith('Traceback'):
                        rows.append(r_s)
            
            print(f"Step {step_num} extracted {len(rows)} valid CSV rows!")
            if len(rows) > 50:
                with open('demo_data/nwkrtc_routes_clean.csv', 'w', encoding='utf-8') as out:
                    out.write('\n'.join(rows))
                print(f"SUCCESS! Saved {len(rows)} rows to demo_data/nwkrtc_routes_clean.csv")
                break
