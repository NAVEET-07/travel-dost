import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        data = json.loads(line)
        content = str(data.get('content', ''))
        if '01,Cbt ⇆ Rajeev Nagar' in content and 'import ' not in content and 'def ' not in content:
            print(f"Step {i}: type={data.get('type')}, source={data.get('source')}, content_len={len(content)}")
            idx = content.find('01,Cbt ⇆ Rajeev Nagar')
            print("Preview near match:", repr(content[idx:idx+200]))
