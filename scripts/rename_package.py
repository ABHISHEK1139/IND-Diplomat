import os
import re

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Files to process
    extensions = ['.py', '.md', '.txt', '.yml', '.yaml', '.ini']
    
    patterns = [
        (re.compile(r'\bdip3\.'), 'dip.'),
        (re.compile(r'src/dip\b'), 'src/dip'),
        (re.compile(r'dip/'), 'dip/'),
        (re.compile(r'\bdip3\b'), 'dip'),
    ]
    
    modified_count = 0
    
    for dirpath, dirnames, filenames in os.walk(root):
        if '.git' in dirnames:
            dirnames.remove('.git')
        if '__pycache__' in dirnames:
            dirnames.remove('__pycache__')
            
        for fname in filenames:
            if not any(fname.endswith(ext) for ext in extensions):
                continue
                
            filepath = os.path.join(dirpath, fname)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                continue
                
            original_content = content
            for pat, repl in patterns:
                content = pat.sub(repl, content)
                
            if content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                modified_count += 1
                print(f"Updated: {os.path.relpath(filepath, root)}")
                
    print(f"\nModified {modified_count} files.")

if __name__ == '__main__':
    main()
