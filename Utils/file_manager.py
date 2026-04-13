"""
File System Manager for IND-Diplomat
Manages uploads, downloads, and context with timestamp-based organization.
"""

import os
import shutil
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import mimetypes


@dataclass
class FileRecord:
    """Record of a file in the system."""
    file_id: str
    filename: str
    filepath: str
    file_type: str
    mime_type: str
    size_bytes: int
    checksum: str
    uploaded_at: str
    user_id: Optional[str] = None  # Owner of the file
    session_id: Optional[str] = None
    context_window_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class FileSystemManager:
    """
    Production-grade file system manager with:
    1. Timestamp-based folder organization
    2. Upload handling for files, folders, images
    3. Download tracking with metadata
    4. Context window association
    5. Time awareness for the model
    """
    
    def __init__(self, base_path: str = "./data"):
        self.base_path = Path(base_path)
        
        # Directory structure
        self.uploads_dir = self.base_path / "uploads"
        self.downloads_dir = self.base_path / "downloads"
        self.contexts_dir = self.base_path / "contexts"
        self.images_dir = self.base_path / "images"
        self.temp_dir = self.base_path / "temp"
        
        # Create directories
        for d in [self.uploads_dir, self.downloads_dir, self.contexts_dir, self.images_dir, self.temp_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # File registry
        self._registry_path = self.base_path / "file_registry.json"
        self._registry: Dict[str, FileRecord] = {}
        self._load_registry()
        
        # Current time awareness
        self._time_offset = 0  # UTC offset in hours
    
    # ============== Time Awareness ==============
    
    def get_current_time(self) -> datetime:
        """Returns current time with timezone awareness."""
        return datetime.now(timezone.utc)
    
    def get_local_time(self, tz_offset_hours: int = 5.5) -> datetime:
        """Returns local time (default: IST +5:30)."""
        from datetime import timedelta
        utc_now = datetime.now(timezone.utc)
        return utc_now + timedelta(hours=tz_offset_hours)
    
    def format_timestamp(self, dt: datetime = None) -> str:
        """Formats timestamp for folder/file naming."""
        if dt is None:
            dt = self.get_current_time()
        return dt.strftime("%Y%m%d_%H%M%S")
    
    def format_display_time(self, dt: datetime = None) -> str:
        """Formats time for display."""
        if dt is None:
            dt = self.get_local_time()
        return dt.strftime("%Y-%m-%d %H:%M:%S IST")
    
    def get_time_context(self) -> Dict[str, Any]:
        """Returns time context for model awareness."""
        now = self.get_local_time()
        return {
            "current_time": self.format_display_time(now),
            "timestamp": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "timezone": "IST (UTC+5:30)",
            "is_business_hours": 9 <= now.hour < 18,
            "period": "morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening" if now.hour < 21 else "night"
        }
    
    # ============== Directory Management ==============
    
    def create_session_folder(self, session_id: str = None) -> Path:
        """Creates a timestamped session folder for uploads."""
        timestamp = self.format_timestamp()
        session_id = session_id or f"session_{timestamp}"
        
        folder_name = f"{timestamp}_{session_id}"
        folder_path = self.uploads_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (folder_path / "documents").mkdir(exist_ok=True)
        (folder_path / "images").mkdir(exist_ok=True)
        (folder_path / "data").mkdir(exist_ok=True)
        
        return folder_path
    
    def create_context_window(self, context_id: str = None) -> Tuple[str, Path]:
        """Creates a context window folder for grouped analysis."""
        timestamp = self.format_timestamp()
        context_id = context_id or f"ctx_{timestamp}"
        
        folder_path = self.contexts_dir / f"{timestamp}_{context_id}"
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # Create context metadata
        metadata = {
            "context_id": context_id,
            "created_at": self.format_display_time(),
            "files": [],
            "status": "active"
        }
        
        with open(folder_path / "context.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return context_id, folder_path
    
    def get_download_path(self, filename: str, source: str = "api") -> Path:
        """Creates timestamped download path."""
        timestamp = self.format_timestamp()
        date_folder = datetime.now().strftime("%Y-%m-%d")
        
        download_folder = self.downloads_dir / date_folder / source
        download_folder.mkdir(parents=True, exist_ok=True)
        
        # Add timestamp to filename to avoid conflicts
        name, ext = os.path.splitext(filename)
        timestamped_name = f"{name}_{timestamp}{ext}"
        
        return download_folder / timestamped_name
    
    # ============== File Operations ==============
    
    def _compute_checksum(self, content: bytes) -> str:
        """Computes SHA256 checksum."""
        return hashlib.sha256(content).hexdigest()[:16]
    
    def _generate_file_id(self, filename: str) -> str:
        """Generates unique file ID."""
        timestamp = self.format_timestamp()
        hash_part = hashlib.md5(f"{filename}{timestamp}".encode()).hexdigest()[:8]
        return f"file_{timestamp}_{hash_part}"
    
    def save_uploaded_file(
        self,
        content: bytes,
        filename: str,
        user_id: str = None,
        session_folder: Path = None,
        context_id: str = None,
        metadata: Dict = None
    ) -> FileRecord:
        """Saves an uploaded file with full tracking and user ownership."""
        # Create session folder if not provided
        if session_folder is None:
            session_folder = self.create_session_folder()
        
        # Determine file type and subfolder
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or "application/octet-stream"
        
        if mime_type.startswith("image/"):
            subfolder = "images"
            file_type = "image"
        elif mime_type.startswith("text/") or mime_type in ["application/pdf", "application/json"]:
            subfolder = "documents"
            file_type = "document"
        else:
            subfolder = "data"
            file_type = "data"
        
        # Save file
        file_path = session_folder / subfolder / filename
        file_path.write_bytes(content)
        
        # Create record with user ownership
        file_id = self._generate_file_id(filename)
        record = FileRecord(
            file_id=file_id,
            filename=filename,
            filepath=str(file_path),
            file_type=file_type,
            mime_type=mime_type,
            size_bytes=len(content),
            checksum=self._compute_checksum(content),
            uploaded_at=self.format_display_time(),
            user_id=user_id,
            session_id=session_folder.name,
            context_window_id=context_id,
            metadata=metadata or {}
        )
        
        # Register
        self._registry[file_id] = record
        self._save_registry()
        
        return record
    
    def save_folder_upload(
        self,
        folder_path: Path,
        session_folder: Path = None,
        context_id: str = None
    ) -> List[FileRecord]:
        """Saves all files from an uploaded folder."""
        if session_folder is None:
            session_folder = self.create_session_folder()
        
        records = []
        
        for file_path in folder_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(folder_path)
                content = file_path.read_bytes()
                
                # Preserve folder structure
                target_folder = session_folder / "data" / relative_path.parent
                target_folder.mkdir(parents=True, exist_ok=True)
                
                record = self.save_uploaded_file(
                    content=content,
                    filename=str(relative_path),
                    session_folder=session_folder,
                    context_id=context_id,
                    metadata={"original_path": str(relative_path)}
                )
                records.append(record)
        
        return records
    
    def save_api_download(
        self,
        content: bytes,
        filename: str,
        source_api: str,
        metadata: Dict = None
    ) -> FileRecord:
        """Saves a file downloaded from an API with full tracking."""
        file_path = self.get_download_path(filename, source_api)
        file_path.write_bytes(content)
        
        file_id = self._generate_file_id(filename)
        mime_type, _ = mimetypes.guess_type(filename)
        
        record = FileRecord(
            file_id=file_id,
            filename=filename,
            filepath=str(file_path),
            file_type="api_download",
            mime_type=mime_type or "application/octet-stream",
            size_bytes=len(content),
            checksum=self._compute_checksum(content),
            uploaded_at=self.format_display_time(),
            metadata={
                "source_api": source_api,
                "downloaded_at": self.format_display_time(),
                **(metadata or {})
            }
        )
        
        self._registry[file_id] = record
        self._save_registry()
        
        return record
    
    def get_file(self, file_id: str) -> Optional[FileRecord]:
        """Gets a file record by ID."""
        return self._registry.get(file_id)
    
    def list_files(
        self,
        session_id: str = None,
        context_id: str = None,
        file_type: str = None,
        date_from: str = None,
        date_to: str = None
    ) -> List[FileRecord]:
        """Lists files with optional filters."""
        results = list(self._registry.values())
        
        if session_id:
            results = [r for r in results if r.session_id == session_id]
        
        if context_id:
            results = [r for r in results if r.context_window_id == context_id]
        
        if file_type:
            results = [r for r in results if r.file_type == file_type]
        
        return results
    
    def get_session_summary(self, session_id: str) -> Dict:
        """Gets summary of a session's files."""
        files = self.list_files(session_id=session_id)
        
        return {
            "session_id": session_id,
            "total_files": len(files),
            "total_size_mb": sum(f.size_bytes for f in files) / (1024 * 1024),
            "file_types": list(set(f.file_type for f in files)),
            "files": [f.to_dict() for f in files]
        }
    
    # ============== Context Window Management ==============
    
    def add_to_context(self, context_id: str, file_ids: List[str]) -> Dict:
        """Adds files to a context window."""
        context_path = None
        
        for folder in self.contexts_dir.iterdir():
            if context_id in folder.name:
                context_path = folder
                break
        
        if not context_path:
            _, context_path = self.create_context_window(context_id)
        
        # Load context metadata
        meta_path = context_path / "context.json"
        with open(meta_path, 'r') as f:
            metadata = json.load(f)
        
        # Add files
        for file_id in file_ids:
            record = self._registry.get(file_id)
            if record:
                metadata["files"].append({
                    "file_id": file_id,
                    "filename": record.filename,
                    "added_at": self.format_display_time()
                })
                record.context_window_id = context_id
        
        metadata["updated_at"] = self.format_display_time()
        
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self._save_registry()
        
        return metadata
    
    def get_context_files(self, context_id: str) -> List[Dict]:
        """Gets all files in a context window."""
        files = self.list_files(context_id=context_id)
        return [
            {
                **f.to_dict(),
                "content_preview": self._get_file_preview(f)
            }
            for f in files
        ]
    
    def _get_file_preview(self, record: FileRecord, max_chars: int = 500) -> str:
        """Gets a preview of file content."""
        try:
            path = Path(record.filepath)
            if not path.exists():
                return "[File not found]"
            
            if record.mime_type.startswith("text/") or record.mime_type == "application/json":
                content = path.read_text(encoding="utf-8", errors="ignore")
                return content[:max_chars] + ("..." if len(content) > max_chars else "")
            elif record.mime_type.startswith("image/"):
                return f"[Image: {record.filename}, {record.size_bytes} bytes]"
            else:
                return f"[Binary file: {record.filename}, {record.size_bytes} bytes]"
        except Exception as e:
            return f"[Error reading file: {e}]"
    
    # ============== Registry Persistence ==============
    
    def _load_registry(self):
        """Loads the file registry from disk."""
        if self._registry_path.exists():
            try:
                with open(self._registry_path, 'r') as f:
                    data = json.load(f)
                    for file_id, record_data in data.items():
                        self._registry[file_id] = FileRecord(**record_data)
            except Exception as e:
                print(f"[FileManager] Error loading registry: {e}")
    
    def _save_registry(self):
        """Saves the file registry to disk."""
        try:
            data = {fid: r.to_dict() for fid, r in self._registry.items()}
            with open(self._registry_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[FileManager] Error saving registry: {e}")
    
    # ============== Cleanup ==============
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """[DEVELOPER API] Removes files older than specified days."""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days_old)
        removed = 0
        
        for file_id, record in list(self._registry.items()):
            try:
                uploaded = datetime.strptime(record.uploaded_at.split(" IST")[0], "%Y-%m-%d %H:%M:%S")
                if uploaded < cutoff:
                    path = Path(record.filepath)
                    if path.exists():
                        path.unlink()
                    del self._registry[file_id]
                    removed += 1
            except:
                pass
        
        self._save_registry()
        return removed
    
    def get_storage_stats(self) -> Dict:
        """[DEVELOPER API] Returns storage statistics."""
        total_size = sum(r.size_bytes for r in self._registry.values())
        
        by_type = {}
        for r in self._registry.values():
            by_type[r.file_type] = by_type.get(r.file_type, 0) + r.size_bytes
        
        return {
            "total_files": len(self._registry),
            "total_size_mb": total_size / (1024 * 1024),
            "by_type": {k: v / (1024 * 1024) for k, v in by_type.items()},
            "uploads_dir": str(self.uploads_dir),
            "downloads_dir": str(self.downloads_dir)
        }
    
    # ============== User-Scoped Operations (End User API) ==============
    
    def list_user_files(self, user_id: str) -> List[FileRecord]:
        """
        [END USER API] Lists only files owned by specified user.
        Users can only see their own files.
        """
        return [r for r in self._registry.values() if r.user_id == user_id]
    
    def get_user_file(self, file_id: str, user_id: str) -> Optional[FileRecord]:
        """
        [END USER API] Gets a file only if owned by user.
        """
        record = self._registry.get(file_id)
        if record and record.user_id == user_id:
            return record
        return None
    
    def delete_user_file(self, file_id: str, user_id: str) -> Tuple[bool, str]:
        """
        [END USER API] Deletes a file only if owned by user.
        Returns (success, message).
        """
        record = self._registry.get(file_id)
        
        if not record:
            return False, "File not found"
        
        if record.user_id != user_id:
            return False, "Access denied: You can only delete your own files"
        
        try:
            path = Path(record.filepath)
            if path.exists():
                path.unlink()
            del self._registry[file_id]
            self._save_registry()
            return True, f"File '{record.filename}' deleted successfully"
        except Exception as e:
            return False, f"Error deleting file: {e}"
    
    def get_user_storage_stats(self, user_id: str) -> Dict:
        """
        [END USER API] Gets storage stats for a specific user.
        """
        user_files = self.list_user_files(user_id)
        total_size = sum(f.size_bytes for f in user_files)
        
        return {
            "user_id": user_id,
            "total_files": len(user_files),
            "total_size_mb": total_size / (1024 * 1024),
            "files": [{"file_id": f.file_id, "filename": f.filename, 
                       "size_kb": f.size_bytes / 1024, "uploaded_at": f.uploaded_at}
                      for f in user_files]
        }
    
    def delete_all_user_files(self, user_id: str) -> Tuple[int, str]:
        """
        [END USER API] Deletes all files owned by user.
        """
        user_files = self.list_user_files(user_id)
        deleted = 0
        
        for record in user_files:
            try:
                path = Path(record.filepath)
                if path.exists():
                    path.unlink()
                del self._registry[record.file_id]
                deleted += 1
            except:
                pass
        
        self._save_registry()
        return deleted, f"Deleted {deleted} files"


# Singleton instance
file_manager = FileSystemManager()
