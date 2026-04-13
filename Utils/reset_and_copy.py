
import shutil
import os
import time

SOURCE_DIR = r"c:\Users\ak612\OneDrive\Desktop\New folder  new ai"
DEST_DIR = r"c:\Users\ak612\OneDrive\Desktop\New folder  new ai\aiiiii dip"

def reset_and_copy():
    # 1. Delete destination if exists
    if os.path.exists(DEST_DIR):
        print(f"Removing {DEST_DIR}...")
        try:
            shutil.rmtree(DEST_DIR)
        except Exception as e:
            print(f"Error removing directory: {e}")
            # Try a retrying approach or just fail? 
            # Let's try to rename it then delete on exit execution? No.
            return

    # Wait a moment for filesystem to release locks
    time.sleep(1)

    # 2. Copy source to destination
    print(f"Copying {SOURCE_DIR} to {DEST_DIR}...")
    
    def ignore_patterns(path, names):
        # Ignore .git, .idea, __pycache__, and the destination folder itself to avoid recursion
        ignored = {'.git', '.idea', '__pycache__', 'aiiiii dip', 'venv', '.venv'}
        return {name for name in names if name in ignored}

    try:
        shutil.copytree(SOURCE_DIR, DEST_DIR, ignore=ignore_patterns)
        print("Copy complete!")
    except Exception as e:
        print(f"Error copying: {e}")

if __name__ == "__main__":
    reset_and_copy()
