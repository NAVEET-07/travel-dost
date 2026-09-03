import json

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line_num, line in enumerate(f):
        data = json.loads(line)
        if data.get('type') == 'USER_INPUT':
            content = str(data.get('content', ''))
            print(f"Step {line_num} USER_INPUT length: {len(content)}")
            print("First 200 chars:", repr(content[:200]))
            print("Last 200 chars:", repr(content[-200:]))
