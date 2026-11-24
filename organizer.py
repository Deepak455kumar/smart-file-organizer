"""Core organization engine for Smart File Organizer.

Handles safe file categorization, preview generation, duplicate collision avoidance,
safe file moves, undo manifests, and path protection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple
import json
import logging
import os
import shutil

from config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_CATEGORY,
    EXTENSION_CATEGORIES,
    INTERNAL_PROTECTED_DIRS,
    INTERNAL_PROTECTED_FILES,
    LOG_FILENAME,
    MANIFEST_FILENAME,
    SYSTEM_PROTECTED_DIR_NAMES,
)

logger = logging.getLogger("smart_file_organizer")


@dataclass
class PreviewItem:
    """Represents a proposed file movement during preview."""

    filename: str
    source_path: Path
    category: str
    destination_folder: Path
    destination_path: Path
    is_duplicate: bool = False
    original_size: int = 0
    status: str = "Ready"
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "source_path": str(self.source_path),
            "category": self.category,
            "destination_folder": str(self.destination_folder),
            "destination_path": str(self.destination_path),
            "is_duplicate": self.is_duplicate,
            "original_size": self.original_size,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass
class OperationItem:
    """Record of a successfully executed move."""

    source_path: str
    destination_path: str
    category: str
    filename: str
    final_filename: str
    file_size: int
    mtime: float


@dataclass
class OperationResult:
    """Summary of an organization run."""

    total_eligible: int = 0
    moved_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    moved_items: List[OperationItem] = field(default_factory=list)
    skipped_items: List[Tuple[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class UndoResult:
    """Summary of an undo operation."""

    total_attempted: int = 0
    restored_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    restored_items: List[str] = field(default_factory=list)
    skipped_items: List[Tuple[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class FileOrganizer:
    """Main engine responsible for directory analysis, file organization, and undo."""

    def __init__(self, log_to_file: bool = True, log_dir: Optional[Path] = None):
        self.latest_manifest: Optional[dict] = None
        self._setup_logging(log_to_file, log_dir)

    def _setup_logging(self, log_to_file: bool, log_dir: Optional[Path]) -> None:
        """Configure structured logging for the organizer."""
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # File handler
            if log_to_file:
                target_dir = log_dir if log_dir else Path.cwd()
                log_file_path = target_dir / LOG_FILENAME
                try:
                    file_handler = logging.FileHandler(
                        log_file_path, encoding="utf-8"
                    )
                    file_handler.setFormatter(formatter)
                    logger.addHandler(file_handler)
                except Exception as err:
                    logger.warning("Could not initialize file log handler: %s", err)

    @staticmethod
    def get_category(extension_or_filename: str) -> str:
        """Determine category from an extension or full filename.

        Matching is case-insensitive.
        """
        ext = extension_or_filename.strip().lower()
        if not ext.startswith("."):
            ext = Path(extension_or_filename).suffix.lower()

        for category, extensions in EXTENSION_CATEGORIES.items():
            if ext in extensions:
                return category
        return DEFAULT_CATEGORY

    @staticmethod
    def is_protected_directory(path: Path) -> Tuple[bool, str]:
        """Validate if a directory is safe to organize.

        Rejects filesystem roots, Windows system directories, and user profile roots.
        """
        try:
            resolved = path.resolve()
        except Exception as err:
            return True, f"Invalid or inaccessible path: {err}"

        if not resolved.exists():
            return True, "Directory does not exist."

        if not resolved.is_dir():
            return True, "Path is not a directory."

        # Reject filesystem roots (e.g., C:\, E:\, /)
        if resolved.parent == resolved or resolved == Path(resolved.anchor):
            return True, f"Rejected: '{resolved}' is a filesystem root drive. Direct organization is not allowed for safety."

        # Reject direct user home profile directory (e.g., C:\Users\Username)
        try:
            user_home = Path.home().resolve()
            if resolved == user_home:
                return (
                    True,
                    "Rejected: Cannot organize the user profile root directory directly. "
                    "Please select a specific folder (e.g., Downloads, Documents, or a test folder).",
                )
        except Exception:
            pass

        # Reject Windows system directories and anything inside them
        env_win = os.environ.get("SystemRoot") or os.environ.get("windir") or "C:\\Windows"
        try:
            resolved_win = Path(env_win).resolve()
            if resolved == resolved_win or resolved_win in resolved.parents:
                return True, f"Rejected: Protected Windows system directory ({resolved})."
        except Exception:
            pass

        # Reject Program Files and ProgramData directories
        env_program_roots = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("ProgramData"),
        ]
        for env_path in env_program_roots:
            if env_path:
                try:
                    resolved_prog = Path(env_path).resolve()
                    if resolved == resolved_prog or resolved_prog in resolved.parents:
                        return True, f"Rejected: Protected program directory ({resolved})."
                except Exception:
                    continue

        # Reject direct selection of specific system folder names
        dir_name_lower = resolved.name.lower()
        critical_system_names = {
            "windows",
            "system32",
            "syswow64",
            "program files",
            "program files (x86)",
            "programdata",
            "recovery",
            "system volume information",
            "$recycle.bin",
            "boot",
            "perflogs",
            "appdata",
        }
        if dir_name_lower in critical_system_names:
            return True, f"Rejected: '{resolved.name}' is a protected system directory."

        # Reject direct AppData roots
        for env_appdata in (os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA")):
            if env_appdata:
                try:
                    if resolved == Path(env_appdata).resolve():
                        return True, f"Rejected: Protected application data folder ({resolved.name})."
                except Exception:
                    pass

        return False, "Directory is safe."

    @staticmethod
    def is_internal_protected(file_path: Path, target_dir: Path) -> bool:
        """Check if a file belongs to the application workspace or internal metadata."""
        filename = file_path.name
        if filename in INTERNAL_PROTECTED_FILES:
            return True
        if filename.startswith("."):
            return True
        for parent in file_path.parents:
            if parent == target_dir:
                break
            if parent.name in INTERNAL_PROTECTED_DIRS or parent.name.startswith("."):
                return True
        return False

    @staticmethod
    def generate_unique_destination(
        dest_folder: Path, filename: str, reserved_paths: Optional[Set[Path]] = None
    ) -> Tuple[Path, bool]:
        """Generate a safe, unique destination path avoiding collisions.

        If target file exists or is reserved by an earlier item in the batch,
        appends _1, _2, etc. (e.g. report.pdf -> report_1.pdf).
        Returns (unique_path, was_renamed).
        """
        reserved = reserved_paths if reserved_paths is not None else set()
        dest_path = dest_folder / filename
        if not dest_path.exists() and dest_path not in reserved:
            return dest_path, False

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1

        while True:
            candidate_name = f"{stem}_{counter}{suffix}"
            candidate_path = dest_folder / candidate_name
            if not candidate_path.exists() and candidate_path not in reserved:
                return candidate_path, True
            counter += 1

    def preview_organization(self, directory: Path | str) -> Tuple[List[PreviewItem], List[str]]:
        """Scan directory and produce a proposed move list without modifying any files.

        Returns (preview_items, warnings).
        """
        dir_path = Path(directory)
        warnings: List[str] = []

        is_protected, reason = self.is_protected_directory(dir_path)
        if is_protected:
            raise PermissionError(reason)

        preview_items: List[PreviewItem] = []
        reserved_destinations: Set[Path] = set()

        # Known category folder names to avoid moving them into themselves
        category_folders = set(EXTENSION_CATEGORIES.keys()) | {DEFAULT_CATEGORY}

        try:
            with os.scandir(dir_path) as entries:
                for entry in entries:
                    try:
                        # Skip symlinks (never follow or move symlinks per requirements)
                        if entry.is_symlink():
                            warnings.append(f"Skipped symlink: {entry.name}")
                            continue

                        # Non-recursive in v1: skip subdirectories
                        if entry.is_dir():
                            continue

                        entry_path = Path(entry.path)

                        # Skip internal protected files (e.g. manifest, main.py, dotfiles)
                        if self.is_internal_protected(entry_path, dir_path):
                            continue

                        # Categorize file
                        category = self.get_category(entry_path.suffix)
                        dest_folder = dir_path / category

                        # Check destination collision
                        dest_path, was_renamed = self.generate_unique_destination(
                            dest_folder, entry_path.name, reserved_destinations
                        )
                        reserved_destinations.add(dest_path)

                        try:
                            stat_info = entry.stat()
                            file_size = stat_info.st_size
                        except OSError:
                            file_size = 0

                        item = PreviewItem(
                            filename=entry.name,
                            source_path=entry_path,
                            category=category,
                            destination_folder=dest_folder,
                            destination_path=dest_path,
                            is_duplicate=was_renamed,
                            original_size=file_size,
                            status="Renamed" if was_renamed else "Ready",
                            reason=f"Renamed to avoid collision with existing {dest_path.name}"
                            if was_renamed
                            else "",
                        )
                        preview_items.append(item)

                    except (PermissionError, OSError) as entry_err:
                        warnings.append(f"Inaccessible file {entry.name}: {entry_err}")

        except (PermissionError, OSError) as dir_err:
            raise PermissionError(f"Cannot read directory: {dir_err}") from dir_err

        # Sort preview items alphabetically for clean display
        preview_items.sort(key=lambda x: (x.category, x.filename.lower()))
        logger.info(
            "Preview generated for '%s': %d eligible files found.",
            dir_path,
            len(preview_items),
        )
        return preview_items, warnings

    def organize_files(
        self,
        directory: Path | str,
        preview_items: Optional[List[PreviewItem]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> OperationResult:
        """Execute the organization of files into category folders safely.

        Creates category folders on-demand.
        Records an operation manifest for safe undo.
        Never overwrites files.
        """
        dir_path = Path(directory)
        is_protected, reason = self.is_protected_directory(dir_path)
        if is_protected:
            raise PermissionError(reason)

        if preview_items is None:
            preview_items, _ = self.preview_organization(dir_path)

        result = OperationResult(total_eligible=len(preview_items))
        if not preview_items:
            logger.info("No eligible files to organize in '%s'.", dir_path)
            return result

        manifest_items: List[dict] = []
        created_folders: Set[Path] = set()

        total = len(preview_items)
        for index, item in enumerate(preview_items, start=1):
            if progress_callback:
                progress_callback(index, total, item.filename)

            # Re-verify source file exists and is accessible
            if not item.source_path.exists():
                msg = f"Source file no longer exists: {item.source_path.name}"
                result.skipped_count += 1
                result.skipped_items.append((item.filename, msg))
                logger.warning(msg)
                continue

            # Verify source is not a symlink
            if item.source_path.is_symlink():
                msg = f"Skipping symlink encountered during execution: {item.filename}"
                result.skipped_count += 1
                result.skipped_items.append((item.filename, msg))
                logger.warning(msg)
                continue

            # Check if destination folder exists, create on demand
            try:
                if not item.destination_folder.exists():
                    item.destination_folder.mkdir(parents=True, exist_ok=True)
                    created_folders.add(item.destination_folder)
            except OSError as mkdir_err:
                msg = f"Failed to create category folder '{item.category}': {mkdir_err}"
                result.error_count += 1
                result.errors.append(msg)
                logger.error(msg)
                continue

            # Final destination check to guarantee we never overwrite
            final_dest = item.destination_path
            if final_dest.exists():
                # Re-compute unique destination in case a file appeared
                final_dest, _ = self.generate_unique_destination(
                    item.destination_folder, item.destination_path.name
                )

            # Record file stat prior to move for verification
            try:
                stat_before = item.source_path.stat()
                file_size = stat_before.st_size
                mtime = stat_before.st_mtime
            except OSError as stat_err:
                msg = f"Cannot read stat for '{item.filename}': {stat_err}"
                result.error_count += 1
                result.errors.append(msg)
                logger.error(msg)
                continue

            # Perform the safe move
            try:
                shutil.move(str(item.source_path), str(final_dest))
                op_item = OperationItem(
                    source_path=str(item.source_path.resolve()),
                    destination_path=str(final_dest.resolve()),
                    category=item.category,
                    filename=item.filename,
                    final_filename=final_dest.name,
                    file_size=file_size,
                    mtime=mtime,
                )
                result.moved_count += 1
                result.moved_items.append(op_item)
                manifest_items.append(
                    {
                        "source_path": op_item.source_path,
                        "destination_path": op_item.destination_path,
                        "category": op_item.category,
                        "filename": op_item.filename,
                        "final_filename": op_item.final_filename,
                        "file_size": op_item.file_size,
                        "mtime": op_item.mtime,
                    }
                )
                logger.info(
                    "Moved: '%s' -> '%s'",
                    item.filename,
                    final_dest.relative_to(dir_path),
                )
            except (PermissionError, OSError) as move_err:
                msg = f"Failed to move '{item.filename}': {move_err}"
                result.error_count += 1
                result.errors.append(msg)
                logger.error(msg)

        # Write manifest file to the target directory
        if manifest_items:
            manifest_data = {
                "app_name": APP_NAME,
                "app_version": APP_VERSION,
                "timestamp": datetime.now().isoformat(),
                "target_directory": str(dir_path.resolve()),
                "total_moved": len(manifest_items),
                "items": manifest_items,
            }
            manifest_file = dir_path / MANIFEST_FILENAME
            try:
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(manifest_data, f, indent=2)
                self.latest_manifest = manifest_data
                logger.info(
                    "Operation manifest saved with %d items at '%s'",
                    len(manifest_items),
                    manifest_file,
                )
            except OSError as manifest_err:
                logger.error("Failed to write manifest file: %s", manifest_err)
                result.errors.append(f"Manifest write failed: {manifest_err}")

        return result

    def get_manifest(self, directory: Path | str) -> Optional[dict]:
        """Load manifest from directory or memory."""
        dir_path = Path(directory)
        manifest_file = dir_path / MANIFEST_FILENAME
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.latest_manifest = data
                    return data
            except Exception as err:
                logger.warning("Failed to parse manifest at '%s': %s", manifest_file, err)
                return None
        return self.latest_manifest

    def undo_last_operation(
        self,
        directory: Path | str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> UndoResult:
        """Undo the last file organization using the operation manifest.

        Verifies that files have not been modified and original paths are available.
        Performs safe restoration without deleting or overwriting user files.
        Cleans up empty category folders.
        """
        dir_path = Path(directory)
        manifest = self.get_manifest(dir_path)

        if not manifest or "items" not in manifest or not manifest["items"]:
            return UndoResult(errors=["No undo manifest found for this directory."])

        items = manifest["items"]
        result = UndoResult(total_attempted=len(items))
        remaining_items: List[dict] = []
        affected_folders: Set[Path] = set()

        total = len(items)
        for index, item in enumerate(items, start=1):
            source_path = Path(item["source_path"])
            dest_path = Path(item["destination_path"])
            filename = item.get("filename", source_path.name)

            if progress_callback:
                progress_callback(index, total, filename)

            # Check if moved file exists in destination
            if not dest_path.exists():
                msg = f"Destination file not found: {dest_path.name}"
                result.skipped_count += 1
                result.skipped_items.append((filename, msg))
                remaining_items.append(item)
                logger.warning(msg)
                continue

            # Verify file has not been modified since organization
            try:
                curr_stat = dest_path.stat()
                # Check size match
                expected_size = item.get("file_size")
                if expected_size is not None and curr_stat.st_size != expected_size:
                    msg = (
                        f"File '{filename}' was modified after organization "
                        f"(size changed from {expected_size} to {curr_stat.st_size}). Skipping undo."
                    )
                    result.skipped_count += 1
                    result.skipped_items.append((filename, msg))
                    remaining_items.append(item)
                    logger.warning(msg)
                    continue
            except OSError as stat_err:
                msg = f"Cannot inspect file '{dest_path.name}': {stat_err}"
                result.error_count += 1
                result.errors.append(msg)
                remaining_items.append(item)
                logger.error(msg)
                continue

            # Verify original source path is free (never overwrite!)
            if source_path.exists():
                msg = f"Original location is already occupied: {source_path.name}. Skipping undo to prevent overwrite."
                result.skipped_count += 1
                result.skipped_items.append((filename, msg))
                remaining_items.append(item)
                logger.warning(msg)
                continue

            # Move file back
            try:
                affected_folders.add(dest_path.parent)
                shutil.move(str(dest_path), str(source_path))
                result.restored_count += 1
                result.restored_items.append(filename)
                logger.info("Restored: '%s' -> '%s'", dest_path.name, source_path)
            except (PermissionError, OSError) as undo_err:
                msg = f"Failed to restore '{filename}': {undo_err}"
                result.error_count += 1
                result.errors.append(msg)
                remaining_items.append(item)
                logger.error(msg)

        # Clean up empty category folders that were left vacant
        for folder in affected_folders:
            try:
                if folder.exists() and folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
                    logger.info("Removed empty category folder: %s", folder.name)
            except OSError:
                pass  # Folder not empty or cannot be removed, safe to ignore

        # Update or remove manifest
        manifest_file = dir_path / MANIFEST_FILENAME
        if remaining_items:
            # Update manifest with remaining items that could not be restored
            manifest["items"] = remaining_items
            manifest["total_moved"] = len(remaining_items)
            try:
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)
                self.latest_manifest = manifest
            except OSError:
                pass
        else:
            # Everything was successfully restored: remove manifest
            try:
                if manifest_file.exists():
                    manifest_file.unlink()
                self.latest_manifest = None
                logger.info("Undo complete. Manifest removed.")
            except OSError as rm_err:
                logger.warning("Could not delete manifest file: %s", rm_err)

        return result
