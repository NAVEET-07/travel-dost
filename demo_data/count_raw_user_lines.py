import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Find the last USER_REQUEST step with bus_no
pos = text.rfind('01,Cbt ⇆ Rajeev Nagar')
print(f"Position of dataset: {pos}")

if pos != -1:
    snippet = text[pos:]
    end_tag = snippet.find('</USER_REQUEST>')
    if end_tag != -1:
        snippet = snippet[:end_tag]
    
    snippet_clean = snippet.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    lines = [l.strip() for l in snippet_clean.splitlines() if l.strip() and ',' in l]
    print(f"Total CSV lines in user upload text: {len(lines)}")
    
    # Check for duplicates or malformed rows
    bus_nos = []
    keys = []
    dup_keys = []
    
    for idx, l in enumerate(lines, start=1):
        parts = l.split(',', 2)
        if len(parts) == 3:
            bno = parts[0].strip()
            rname = parts[1].strip()
            stops = parts[2].strip()
            bus_nos.append(bno)
            key = (bno, rname, stops)
            if key in keys:
                dup_keys.append((idx, bno, rname))
            else:
                keys.append(key)
        else:
            print(f"Line {idx} does not have 3 CSV fields: {l[:50]}")
            
    print(f"Total lines: {len(lines)}")
    print(f"Total unique keys: {len(keys)}")
    print(f"Total duplicates in raw CSV file: {len(dup_keys)}")
    if dup_keys:
        print("First 5 duplicate lines in user CSV:")
        for d in dup_keys[:5]:
            print(f"  Line {d[0]}: bus_no={d[1]}, route={d[2]}")
