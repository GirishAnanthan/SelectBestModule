import re

with open("d:/SelectBestModule/streamlit_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Pattern to match the section_heading function calls
pattern = r'[ \t]*section_heading\(\s*\"[^\"]*\",\s*\"[^\"]*\",\s*\"[^\"]*\",?\s*\)\n'

new_content = re.sub(pattern, '', content)

if new_content != content:
    with open("d:/SelectBestModule/streamlit_app.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Replaced section_heading calls successfully.")
else:
    print("No changes made.")
