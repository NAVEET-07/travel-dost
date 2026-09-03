import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = '01,Cbt ⇆ Rajeev Nagar,Cbt →'
matches = [m.start() for m in re.finditer(re.escape(target), text)]
print(f"Found {len(matches)} occurrences of target string at positions: {matches}")

for m in matches:
    chunk = text[m:m+200000]
    end_tag = chunk.find('</USER_REQUEST>')
    if end_tag != -1:
        chunk = chunk[:end_tag]
    
    clean_chunk = chunk.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    lines = [l.strip() for l in clean_chunk.splitlines() if ',' in l and ('→' in l or '⇆' in l or 'bus_no' in l)]
    print(f"Occurrence at pos {m}: {len(lines)} CSV lines")
    if len(lines) > 50:
        bus_nos = []
        keys = []
        dups = []
        for idx, l in enumerate(lines, 1):
            parts = l.split(',', 2)
            if len(parts) == 3:
                key = (parts[0].strip(), parts[1].strip(), parts[2].strip())
                if key in keys:
                    dups.append((idx, parts[0].strip(), parts[1].strip()))
                else:
                    keys.append(key)
        print(f"  Total lines in CSV: {len(lines)}")
        print(f"  Unique routes: {len(keys)}")
        print(f"  Duplicate lines: {len(dups)}")
        if dups:
            print("  First 10 duplicates:")
            for d in dups[:10]:
                print(f"    Line {d[0]}: bus_no={d[1]}, route={d[2]}")
        
        with open('demo_data/raw_uploaded_410.csv', 'w', encoding='utf-8') as out:
            out.write('\n'.join(lines))
        print("  Saved demo_data/raw_uploaded_410.csv!")
        break
