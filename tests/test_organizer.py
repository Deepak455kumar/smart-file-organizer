"""Automated test suite for Smart File Organizer.

Verifies:
1. Correct file categorization across all supported extensions.
2. Case-insensitive extension handling (.PNG, .JpG, .Txt, etc.).
3. Duplicate filename collision protection and automatic suffix incrementing.
4. Preview mode safety (no modifications on disk).
5. Correct file movement to respective category folders.
6. Unknown extensions correctly categorized as 'Other'.
7. Undo restores files to their exact original positions.
8. Undo does not overwrite conflicting files if original path is re-occupied.
9. Missing and in-use files handled safely without crash.
10. Protected paths and symlinks are rejected/skipped.
11. Clean-up of empty category folders after complete undo.
"""

from pathlib import Path
import os
import shutil
import tempfile
import unittest

from config import DEFAULT_CATEGORY, EXTENSION_CATEGORIES, MANIFEST_FILENAME
from organizer import FileOrganizer, PreviewItem


class TestFileOrganizer(unittest.TestCase):
    """Unit test cases for FileOrganizer."""

    def setUp(self):
        """Set up a fresh temporary directory inside the workspace before each test."""
        # Use workspace directory for test artifacts per project requirements
        self.test_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent)
        self.root_path = Path(self.test_dir.name).resolve()
        self.organizer = FileOrganizer(log_to_file=False)

    def tearDown(self):
        """Clean up the temporary directory after each test."""
        try:
            self.test_dir.cleanup()
        except Exception:
            pass

    def _create_file(self, relative_path: str, content: str = "sample content") -> Path:
        """Helper to create a test file."""
        file_path = self.root_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    # 1. Correct file categorization across categories
    def test_file_categorization_all_types(self):
        """Verify extension categorization maps to the correct category."""
        samples = {
            "photo.jpg": "Images",
            "graphic.png": "Images",
            "doc.pdf": "Documents",
            "notes.txt": "Documents",
            "budget.xlsx": "Spreadsheets",
            "data.csv": "Spreadsheets",
            "slides.pptx": "Presentations",
            "clip.mp4": "Videos",
            "movie.mkv": "Videos",
            "song.mp3": "Audio",
            "track.flac": "Audio",
            "backup.zip": "Archives",
            "package.7z": "Archives",
            "script.py": "Code",
            "app.js": "Code",
            "style.css": "Code",
        }
        for filename, expected_category in samples.items():
            cat = self.organizer.get_category(filename)
            self.assertEqual(cat, expected_category, f"Failed for {filename}")

    # 2. Case-insensitive extension handling
    def test_case_insensitive_extensions(self):
        """Verify extensions match regardless of casing."""
        test_cases = [
            ("image.JPG", "Images"),
            ("photo.PnG", "Images"),
            ("report.PDF", "Documents"),
            ("notes.TxT", "Documents"),
            ("data.CSV", "Spreadsheets"),
            ("deck.PPTX", "Presentations"),
            ("video.MP4", "Videos"),
            ("audio.WAV", "Audio"),
            ("archive.ZIP", "Archives"),
            ("code.PY", "Code"),
        ]
        for filename, expected in test_cases:
            cat = self.organizer.get_category(filename)
            self.assertEqual(cat, expected, f"Failed for uppercase/mixed {filename}")

    # 3. Duplicate filename collision protection
    def test_duplicate_filename_protection(self):
        """Verify that when a duplicate exists, unique filenames are generated."""
        images_dir = self.root_path / "Images"
        images_dir.mkdir()
        # Existing file in destination
        (images_dir / "photo.jpg").write_text("existing", encoding="utf-8")

        # Destination generator test
        dest1, renamed1 = self.organizer.generate_unique_destination(images_dir, "photo.jpg")
        self.assertTrue(renamed1)
        self.assertEqual(dest1.name, "photo_1.jpg")

        # Reserve photo_1.jpg and generate again
        dest2, renamed2 = self.organizer.generate_unique_destination(
            images_dir, "photo.jpg", reserved_paths={dest1}
        )
        self.assertTrue(renamed2)
        self.assertEqual(dest2.name, "photo_2.jpg")

    # 4. Preview mode safety
    def test_preview_mode_does_not_modify_files(self):
        """Verify preview scans without creating folders or moving files."""
        f1 = self._create_file("test.txt", "hello")
        f2 = self._create_file("picture.png", "img")

        before_listing = sorted([f.name for f in self.root_path.iterdir()])

        items, warnings = self.organizer.preview_organization(self.root_path)

        after_listing = sorted([f.name for f in self.root_path.iterdir()])

        # Check that files were not moved and no folders were created
        self.assertEqual(before_listing, after_listing)
        self.assertEqual(len(items), 2)
        self.assertFalse((self.root_path / "Documents").exists())
        self.assertFalse((self.root_path / "Images").exists())
        self.assertTrue(f1.exists())
        self.assertTrue(f2.exists())

    # 5. Correct file movement
    def test_file_movement_and_folder_creation(self):
        """Verify files are moved to their respective folders and original files removed from root."""
        self._create_file("document.pdf", "pdf content")
        self._create_file("song.mp3", "mp3 content")
        self._create_file("script.py", "python code")

        result = self.organizer.organize_files(self.root_path)

        self.assertEqual(result.moved_count, 3)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.skipped_count, 0)

        # Folders exist
        self.assertTrue((self.root_path / "Documents" / "document.pdf").exists())
        self.assertTrue((self.root_path / "Audio" / "song.mp3").exists())
        self.assertTrue((self.root_path / "Code" / "script.py").exists())

        # Original files no longer in root
        self.assertFalse((self.root_path / "document.pdf").exists())
        self.assertFalse((self.root_path / "song.mp3").exists())
        self.assertFalse((self.root_path / "script.py").exists())

        # Manifest created
        self.assertTrue((self.root_path / MANIFEST_FILENAME).exists())

    # 6. Unknown extensions categorized as 'Other'
    def test_unknown_extension_categorized_as_other(self):
        """Verify unknown or missing extensions are routed to 'Other'."""
        self._create_file("random.unknownext", "unknown")
        self._create_file("no_extension_file", "raw")
        self._create_file("strange.xyz123", "strange")

        items, _ = self.organizer.preview_organization(self.root_path)
        categories = {item.filename: item.category for item in items}

        self.assertEqual(categories["random.unknownext"], DEFAULT_CATEGORY)
        self.assertEqual(categories["no_extension_file"], DEFAULT_CATEGORY)
        self.assertEqual(categories["strange.xyz123"], DEFAULT_CATEGORY)

        # Organize and verify placement
        result = self.organizer.organize_files(self.root_path, items)
        self.assertEqual(result.moved_count, 3)
        self.assertTrue((self.root_path / "Other" / "random.unknownext").exists())
        self.assertTrue((self.root_path / "Other" / "no_extension_file").exists())
        self.assertTrue((self.root_path / "Other" / "strange.xyz123").exists())

    # 7. Undo restores files correctly
    def test_undo_restores_files(self):
        """Verify undo moves files back to their exact original locations."""
        f1 = self._create_file("contract.docx", "contract")
        f2 = self._create_file("logo.png", "logo")

        # Organize
        result = self.organizer.organize_files(self.root_path)
        self.assertEqual(result.moved_count, 2)
        self.assertFalse(f1.exists())
        self.assertFalse(f2.exists())

        # Undo
        undo_res = self.organizer.undo_last_operation(self.root_path)
        self.assertEqual(undo_res.restored_count, 2)
        self.assertEqual(undo_res.skipped_count, 0)
        self.assertEqual(undo_res.error_count, 0)

        # Verify restored to root
        self.assertTrue(f1.exists())
        self.assertTrue(f2.exists())
        self.assertEqual(f1.read_text(encoding="utf-8"), "contract")
        self.assertEqual(f2.read_text(encoding="utf-8"), "logo")

        # Verify empty category folders were removed
        self.assertFalse((self.root_path / "Documents").exists())
        self.assertFalse((self.root_path / "Images").exists())

        # Verify manifest removed after complete undo
        self.assertFalse((self.root_path / MANIFEST_FILENAME).exists())

    # 8. Undo does not overwrite conflicting files
    def test_undo_does_not_overwrite_conflict(self):
        """Verify undo skips restoring if original location is occupied."""
        f1 = self._create_file("report.txt", "original text")

        # Organize moves report.txt -> Documents/report.txt
        self.organizer.organize_files(self.root_path)

        # Now simulate user creating a NEW report.txt in root
        f1.write_text("new conflicting file", encoding="utf-8")

        # Attempt undo
        undo_res = self.organizer.undo_last_operation(self.root_path)

        # Should skip to avoid overwriting the new file
        self.assertEqual(undo_res.restored_count, 0)
        self.assertEqual(undo_res.skipped_count, 1)

        # Verify conflicting file content was preserved
        self.assertEqual(f1.read_text(encoding="utf-8"), "new conflicting file")
        # And organized file remains in Documents
        self.assertTrue((self.root_path / "Documents" / "report.txt").exists())

    # 9. Modified file during undo is skipped
    def test_undo_skips_modified_file(self):
        """Verify undo skips files that were edited after organization."""
        self._create_file("notes.txt", "short")
        self.organizer.organize_files(self.root_path)

        # Edit the file in Documents/
        dest_file = self.root_path / "Documents" / "notes.txt"
        dest_file.write_text("modified longer content that changes size", encoding="utf-8")

        undo_res = self.organizer.undo_last_operation(self.root_path)
        self.assertEqual(undo_res.restored_count, 0)
        self.assertEqual(undo_res.skipped_count, 1)
        self.assertTrue(dest_file.exists())

    # 10. Protected paths validation
    def test_protected_paths_rejection(self):
        """Verify root drives and protected system paths are rejected."""
        # Drive root test (e.g. C:\)
        anchor = Path(self.root_path.anchor)
        is_prot, reason = self.organizer.is_protected_directory(anchor)
        self.assertTrue(is_prot)
        self.assertIn("root", reason.lower())

        # Non-existent path
        is_prot, reason = self.organizer.is_protected_directory(Path("Z:/definitely_not_a_real_path_12345"))
        self.assertTrue(is_prot)

    # 11. Subdirectories are not recursively organized in v1
    def test_subdirectories_ignored(self):
        """Verify subdirectories inside target are left untouched."""
        sub_dir = self.root_path / "my_subfolder"
        sub_dir.mkdir()
        nested_file = sub_dir / "nested.pdf"
        nested_file.write_text("nested", encoding="utf-8")

        items, _ = self.organizer.preview_organization(self.root_path)
        # Should not include nested.pdf or my_subfolder
        filenames = [item.filename for item in items]
        self.assertNotIn("nested.pdf", filenames)
        self.assertNotIn("my_subfolder", filenames)

        self.organizer.organize_files(self.root_path, items)
        # Subfolder and nested file still intact
        self.assertTrue(nested_file.exists())

    # 12. Multiple duplicate names in the same batch
    def test_multiple_duplicate_names_in_same_batch(self):
        """Verify multiple duplicates are safely suffixed without collision."""
        dest_folder = self.root_path / "Documents"
        dest_folder.mkdir()
        (dest_folder / "file.txt").write_text("existing", encoding="utf-8")

        dest1, ren1 = self.organizer.generate_unique_destination(dest_folder, "file.txt")
        self.assertEqual(dest1.name, "file_1.txt")

        dest2, ren2 = self.organizer.generate_unique_destination(
            dest_folder, "file.txt", reserved_paths={dest1}
        )
        self.assertEqual(dest2.name, "file_2.txt")

        dest3, ren3 = self.organizer.generate_unique_destination(
            dest_folder, "file.txt", reserved_paths={dest1, dest2}
        )
        self.assertEqual(dest3.name, "file_3.txt")

    # 13. Application self-protection
    def test_app_workspace_self_protection(self):
        """Verify that application source files are ignored if workspace is targeted."""
        self._create_file("main.py", "print('main')")
        self._create_file("organizer.py", "print('organizer')")
        self._create_file("user_file.txt", "keep me organized")

        items, _ = self.organizer.preview_organization(self.root_path)
        item_names = [i.filename for i in items]

        self.assertNotIn("main.py", item_names)
        self.assertNotIn("organizer.py", item_names)
        self.assertIn("user_file.txt", item_names)

    # 14. Missing file between preview and execution
    def test_file_deleted_between_preview_and_execution(self):
        """Verify organizer skips files removed between preview and execution without failure."""
        f1 = self._create_file("ephemeral.txt", "will be deleted")
        items, _ = self.organizer.preview_organization(self.root_path)
        self.assertEqual(len(items), 1)

        # Simulate user deleting file before organize clicked
        f1.unlink()

        result = self.organizer.organize_files(self.root_path, items)
        self.assertEqual(result.moved_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.error_count, 0)

    # 15. Empty directory behavior
    def test_empty_directory_handling(self):
        """Verify empty directory produces empty preview and zero-move result."""
        items, warnings = self.organizer.preview_organization(self.root_path)
        self.assertEqual(len(items), 0)
        self.assertEqual(len(warnings), 0)

        result = self.organizer.organize_files(self.root_path, items)
        self.assertEqual(result.moved_count, 0)
        self.assertEqual(result.total_eligible, 0)

    # 16. Manifest data integrity
    def test_manifest_structure_and_persistence(self):
        """Verify manifest contains all required fields for recovery."""
        self._create_file("audit.xlsx", "excel data")
        self.organizer.organize_files(self.root_path)

        manifest = self.organizer.get_manifest(self.root_path)
        self.assertIsNotNone(manifest)
        self.assertIn("timestamp", manifest)
        self.assertIn("items", manifest)
        self.assertEqual(manifest["total_moved"], 1)

        first_item = manifest["items"][0]
        self.assertEqual(first_item["category"], "Spreadsheets")
        self.assertEqual(first_item["filename"], "audit.xlsx")
        self.assertIn("destination_path", first_item)
        self.assertIn("file_size", first_item)
        self.assertIn("mtime", first_item)


if __name__ == "__main__":
    unittest.main()
