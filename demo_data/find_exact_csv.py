import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    text = f.read()

prefix = '01' + ',Cbt'
suffix = ' → Rajeev Nagar'
target = prefix + suffix

matches = [m.start() for m in re.finditer(re.escape(target), text)]
print(f"Total occurrences of target: {len(matches)} at positions {matches}")

for idx_m, pos in enumerate(matches):
    chunk = text[pos:pos+500000]
    clean_chunk = chunk.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    
    clean_lines = []
    for l in clean_chunk.splitlines():
        l_s = l.strip()
        if (',' in l_s and ('→' in l_s or 'bus_no' in l_s)) or l_s.startswith('bus_no,'):
            if not any(l_s.startswith(kw) for kw in ['{"', 'File ', 'Traceback', 'import ', 'print', 'def ', 'target', 'prefix', 'suffix', 'clean_lines']):
                clean_lines.append(l_s)
            
    print(f"Match {idx_m} at pos {pos}: {len(clean_lines)} lines")
    if len(clean_lines) > 50:
        if not clean_lines[0].startswith('bus_no,'):
            clean_lines.insert(0, "bus_no,route_name,stops_name_between_route")
        print(f"  SUCCESS! Match {idx_m} extracted {len(clean_lines)-1} CSV route rows!")
        print("  Header:", clean_lines[0])
        print("  Row 1:", clean_lines[1])
        print("  Row 2:", clean_lines[2])
        print("  Row -1:", clean_lines[-1])
        with open('demo_data/user_csv_exact_unique.csv', 'w', encoding='utf-8') as out:
            out.write('\n'.join(clean_lines))
        print("  Saved demo_data/user_csv_exact_unique.csv!")
        break
