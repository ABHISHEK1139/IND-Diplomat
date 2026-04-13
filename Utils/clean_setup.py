
import shutil
import os
import time

SOURCE_DIR = r"c:\Users\ak612\OneDrive\Desktop\New folder  new ai"
DEST_DIR = r"c:\Users\ak612\OneDrive\Desktop\New folder  new ai\Clean_Phase_Project"

def setup_clean_env():
    # 1. Delete destination if exists (try once)
    if os.path.exists(DEST_DIR):
        print(f"Cleaning existing {DEST_DIR}...")
        try:
            shutil.rmtree(DEST_DIR)
        except Exception as e:
            print(f"Warning: Could not fully clean destination: {e}")

    # 2. Copy source to destination
    print(f"Copying {SOURCE_DIR} to {DEST_DIR}...")
    
    def ignore_patterns(path, names):
        # Ignore .git, .idea, __pycache__, and destination folders themselves
        ignored = {'.git', '.idea', '__pycache__', 'aiiiii dip', 'Clean_Phase_Project', 'venv', '.venv'}
        return {name for name in names if name in ignored}

    try:
        shutil.copytree(SOURCE_DIR, DEST_DIR, ignore=ignore_patterns)
        print("Copy complete!")
    except Exception as e:
        print(f"Error copying: {e}")

if __name__ == "__main__":
    setup_clean_env()
