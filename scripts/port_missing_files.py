import os
import shutil
import re
from pathlib import Path

def main():
    
    source_dir = Path(r"c:\Users\ak612\OneDrive\Desktop\dip\New folder\DIP_8")
    target_dir = Path(r"c:\Users\ak612\OneDrive\Desktop\dip\New folder\dip 2.0")
    
    files_to_port = {
        # target path : source path
        "layer1_collection/token_juice.py": "engine/Layer1_Data_Acquisition/token_juice.py",
        "layer3_state/graph_manager.py": "engine/Layer3_StateModel/binding/graph_manager.py",
        "legal/legal_reasoner_prompt.py": "Core/legal/legal_reasoner_prompt.py",
        "legal/legal_indexer.py": "Core/legal/legal_indexer.py",
        "legal/legal_loader.py": "Core/legal/legal_loader.py",
        "legal/legal_splitter.py": "Core/legal/legal_splitter.py",
        "legal/legal_output_validator.py": "Core/legal/legal_output_validator.py",
        "layer6_backtesting/evaluator.py": "engine/Layer6_Backtesting/evaluator.py",
        "layer6_backtesting/exporter.py": "engine/Layer6_Backtesting/exporter.py",
        "layer6_presentation/report_templates.py": "reports/report_templates.py" # guessing the location
    }
    
    # Regex to fix imports
    replacements = [
        (r'from Core\.legal', r'from legal'),
        (r'import Core\.legal', r'import legal'),
        (r'from engine\.Layer1_Data_Acquisition', r'from layer1_collection'),
        (r'import engine\.Layer1_Data_Acquisition', r'import layer1_collection'),
        (r'from engine\.Layer3_StateModel\.binding', r'from layer3_state'),
        (r'from engine\.Layer3_StateModel', r'from layer3_state'),
        (r'from engine\.Layer6_Backtesting', r'from layer6_backtesting'),
        (r'from engine\.Layer6_Presentation', r'from layer6_presentation'),
        (r'from Core\.layer2_knowledge', r'from layer2_knowledge'),
        (r'from Core\.layer1_collection', r'from layer1_collection'),
        (r'from Core\.', r'from ')
    ]
    
    for target_rel, source_rel in files_to_port.items():
        source_path = source_dir / source_rel
        target_path = target_dir / target_rel
        
        # Try finding it if the path is wrong
        if not source_path.exists():
            filename = source_path.name
            print(f"Searching for {filename}...")
            found = list(source_dir.rglob(filename))
            valid = [f for f in found if '.venv' not in str(f) and '__pycache__' not in str(f)]
            if valid:
                source_path = valid[0]
                print(f"Found at {source_path}")
            else:
                print(f"NOT FOUND: {filename}")
                continue
            
        print(f"Porting {source_path.relative_to(source_dir)} to {target_rel}")
        os.makedirs(target_path.parent, exist_ok=True)
        
        with open(source_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        for old, new in replacements:
            content = re.sub(old, new, content)
            
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    print("Done porting.")
    

if __name__ == '__main__':
    main()
