
import shutil
import os
import time

SRC = r"c:\Users\ak612\OneDrive\Desktop\New folder  new ai\Clean_Phase_Project"
DST = r"c:\Users\ak612\OneDrive\Desktop\New folder  new ai\aiiiii dip"

def sync_folders():
    print(f"Syncing {SRC} -> {DST}")
    
    # 1. Create DST if not exists
    if not os.path.exists(DST):
        os.makedirs(DST)
        
    # 2. Copy all files from SRC to DST
    # We use robocopy-like logic: walk SRC and copy
    for root, dirs, files in os.walk(SRC):
        # Create corresponding dir in DST
        rel_path = os.path.relpath(root, SRC)
        dst_dir = os.path.join(DST, rel_path)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
            
        for file in files:
            src_file = os.path.join(root, file)
            dst_file = os.path.join(dst_dir, file)
            
            # Copy if size/mtime different or missing
            if not os.path.exists(dst_file) or \
               os.path.getmtime(src_file) > os.path.getmtime(dst_file) or \
               os.path.getsize(src_file) != os.path.getsize(dst_file):
                try:
                    shutil.copy2(src_file, dst_file)
                    print(f"Copied {file}")
                except Exception as e:
                    print(f"Error copying {file}: {e}")

    # 3. Clean up orphans in DST (files in DST not in SRC)
    # This fulfills "delete other file in aiiiii dip"
    for root, dirs, files in os.walk(DST):
        rel_path = os.path.relpath(root, DST)
        src_dir = os.path.join(SRC, rel_path)
        
        # If dir doesn't exist in SRC, remove it from DST
        if not os.path.exists(src_dir):
            try:
                shutil.rmtree(root)
                print(f"Removed orphan dir {rel_path}")
            except Exception as e:
                print(f"Error removing dir {rel_path}: {e}")
            continue # Don't traverse deleted dir

        for file in files:
            src_file = os.path.join(src_dir, file)
            if not os.path.exists(src_file):
                dst_file = os.path.join(root, file)
                try:
                    os.remove(dst_file)
                    print(f"Removed orphan file {file}")
                except Exception as e:
                    print(f"Error removing file {file}: {e}")

if __name__ == "__main__":
    sync_folders()
