import re

filepath = r"c:\Users\ak612\OneDrive\Desktop\dip\New folder\dip 2.0\MASTER_PLAN.md"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# I know these are completed:
completed_tasks = [
    "T4.6", "T6.4", "T7.2", "T7.3", "T7.4", "T7.5", "T7.7", "T8.5", "T8.6", "T10.9",
    "T13.2", "T13.3", "T17.3", "T18.1", "T18.2", "T19.1", "T19.2", "T20.1", "T20.2",
    "T21.1", "T21.2", "T22.1", "T22.2", "T23.1", "T23.2", "T26.1", "T26.2", "T26.3",
    "T26.4", "T26.5", "T26.6", "T27.1", "T27.2", "T27.3", "T27.4", "T27.5", "T27.6",
    "T27.7", "T27.8", "T27.9", "T27.10", "T27.11", "T27.12", "T27.13", "T27.14", "T27.15",
    "T28.1", "T28.2", "T28.3", "T28.4", "T28.5", "T28.6", "T28.7",
    "deploy/prometheus.yml", "deploy/grafana/dashboards/pipeline.json", "deploy/grafana/dashboards/ministers.json",
    "T25.1", "T25.2", "T25.3", "T25.4" # I saw README, CHANGELOG, docs, .github exist
]

# We will check if the line contains the task ID, and if so, change [ ] to [x]
lines = content.split('\n')
for i, line in enumerate(lines):
    if '[ ]' in line:
        for task in completed_tasks:
            if task in line:
                lines[i] = line.replace('[ ]', '[x]')
                break

with open(filepath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
