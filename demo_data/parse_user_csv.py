import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        data = json.loads(line)
        if data.get('type') == 'USER_INPUT':
            content = data.get('content', '')
            print(f"Transcript step {i}: len={len(content)}")
            print("Preview:", repr(content[:200]))
