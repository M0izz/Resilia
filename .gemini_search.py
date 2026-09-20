import os
import re

targets = ["backend", "dashboard"]
results = []

pattern = re.compile(r'(?i)\b(mock|demo|dummy|sample|hardcode|placeholder)\b')

for target in targets:
    for root, dirs, files in os.walk(target):
        if any(skip in root for skip in [".git", "__pycache__", ".pytest_cache"]):
            continue
        for f in files:
            if not f.endswith((".py", ".html", ".json")):
                continue
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                lines = file.readlines()
            for line_no, line in enumerate(lines):
                line_str = line.strip()
                if pattern.search(line_str):
                    # Filter out innocent imports or comments if too noisy
                    if "demo" in f.lower() or "test" in f.lower():
                        continue
                    results.append((path, line_no + 1, line_str[:120]))

print(f"Total occurrences found: {len(results)}")
for r in results[:40]:
    print(f"{r[0]}:{r[1]} -> {r[2]}")
