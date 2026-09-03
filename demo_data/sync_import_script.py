import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('demo_data/nwkrtc_routes_complete.csv', 'r', encoding='utf-8') as f:
    csv_text = f.read().strip()

with open('demo_data/import_filtered_routes.py', 'r', encoding='utf-8') as f:
    py_content = f.read()

idx1 = py_content.find('RAW_USER_BUS_ROUTES_DATA = """')
if idx1 != -1:
    idx2 = py_content.find('"""', idx1 + 30)
    new_py_content = py_content[:idx1 + 30] + '\n' + csv_text + '\n' + py_content[idx2:]
    with open('demo_data/import_filtered_routes.py', 'w', encoding='utf-8') as out:
        out.write(new_py_content)
    print("Successfully updated demo_data/import_filtered_routes.py with complete routes CSV dataset!")
else:
    print("Could not find RAW_USER_BUS_ROUTES_DATA in import_filtered_routes.py")
