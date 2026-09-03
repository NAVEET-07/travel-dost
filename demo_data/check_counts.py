import re

with open('demo_data/import_filtered_routes.py', 'r', encoding='utf-8') as f:
    code = f.read()

idx1 = code.find('RAW_USER_BUS_ROUTES_DATA = """')
idx2 = code.find('"""', idx1 + 30)
raw_data = code[idx1+30:idx2].strip()
lines = [l for l in raw_data.splitlines() if l.strip() and ',' in l]
print(f"Lines in import_filtered_routes.py RAW_USER_BUS_ROUTES_DATA: {len(lines)}")
