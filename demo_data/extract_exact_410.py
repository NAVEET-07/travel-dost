import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Find occurrences of '01,Cbt ⇆ Rajeev Nagar' in user input context
pattern = re.compile(r'bus_no,route_name,stops_name_between_route[\s\S]*?(?=</USER_REQUEST>)')
matches = pattern.findall(text)

raw_csv_block = None
for m in reversed(matches):
    clean = m.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    lines = [l.strip() for l in clean.splitlines() if ',' in l and ('→' in l or '⇆' in l or 'bus_no' in l)]
    if len(lines) > 100:
        raw_csv_block = clean
        print(f"Found match with {len(lines)} CSV rows!")
        break

if not raw_csv_block:
    # Search for all CSV lines starting with bus_no pattern in last step
    lines_all = []
    for line in text.splitlines():
        l_s = line.strip().replace('\\n', '\n').replace('\\"', '"')
        for sub_line in l_s.splitlines():
            s = sub_line.strip()
            if s.startswith('bus_no,') or (',' in s and ('→' in s or '⇆' in s)):
                if not s.startswith('{"') and not s.startswith('File ') and not s.startswith('Traceback') and not s.startswith('import ') and not s.startswith('print') and not s.startswith('def '):
                    lines_all.append(s)
    print(f"Total CSV lines found in transcript: {len(lines_all)}")
    
    # Save clean list
    with open('demo_data/user_csv_410_exact.csv', 'w', encoding='utf-8') as out:
        out.write('\n'.join(lines_all))
    print("Saved to demo_data/user_csv_410_exact.csv")
else:
    rows = [l.strip() for l in raw_csv_block.splitlines() if ',' in l and ('→' in l or '⇆' in l or 'bus_no' in l)]
    print(f"Total rows in dataset: {len(rows)}")
    with open('demo_data/user_csv_410_exact.csv', 'w', encoding='utf-8') as out:
        out.write('\n'.join(rows))
    print("Saved to demo_data/user_csv_410_exact.csv")
