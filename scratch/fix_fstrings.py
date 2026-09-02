import os
import glob

d = 'src/dip/pipeline/deliberation/reasoning/ministers'
for filepath in glob.glob(os.path.join(d, '*_minister.py')):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix hypothesis JSON block
    content = content.replace('Respond in strict JSON:\n{\n    "claim"', 'Respond in strict JSON:\n{{\n    "claim"')
    content = content.replace('"evidence_ids_cited": ["EV_abc123", "EV_def456"]\n}\'\'\'', '"evidence_ids_cited": ["EV_abc123", "EV_def456"]\n}}\'\'\'')
    
    # Fix rebuttal JSON block (for contrarian/etc)
    content = content.replace('Respond in strict JSON:\n{\n    "claim": "Your rebuttal statement"', 'Respond in strict JSON:\n{{\n    "claim": "Your rebuttal statement"')
    content = content.replace('"evidence_ids_cited": ["EV_abc123"]\n}\'\'\'', '"evidence_ids_cited": ["EV_abc123"]\n}}\'\'\'')
    
    # And for contrarian attack block
    content = content.replace('Respond in strict JSON:\n{\n    "claim": "Your challenge statement"', 'Respond in strict JSON:\n{{\n    "claim": "Your challenge statement"')
    content = content.replace('"counter_evidence": ["EV_counter1"]\n}\'\'\'', '"counter_evidence": ["EV_counter1"]\n}}\'\'\'')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
print('Fixed!')
