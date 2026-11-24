"""Main application entry point for Smart File Organizer.

Supports launching the interactive desktop Tkinter application as well as
convenient headless CLI flags for quick preview, organization, and automated workflows.
"""

from pathlib import Path
import argparse
import sys
import tkinter as tk

from config import APP_NAME, APP_VERSION
from gui import SmartFileOrganizerGUI
from organizer import FileOrganizer


def center_window(root: tk.Tk, width: int = 1160, height: int = 760) -> None:
    """Center the Tkinter window on the primary screen."""
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = max(0, int((screen_width - width) / 2))
    y = max(0, int((screen_height - height) / 2))
    root.geometry(f"{width}x{height}+{x}+{y}")


def run_cli_preview(folder_path: str) -> int:
    """Perform a dry-run preview from the command line."""
    organizer = FileOrganizer()
    path = Path(folder_path).resolve()
    print(f"--- {APP_NAME} v{APP_VERSION} CLI Preview ---")
    print(f"Target Directory: {path}")

    try:
        items, warnings = organizer.preview_organization(path)
        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(f" [!] {w}")

        print(f"\nDiscovered {len(items)} eligible file(s) to organize:")
        for item in items:
            status_flag = f" [{item.status}]" if item.is_duplicate else ""
            print(f" • {item.filename:<30} -> {item.category}/{item.destination_path.name}{status_flag}")

        print(f"\nTotal: {len(items)} file(s).")
        return 0
    except Exception as err:
        print(f"\nError: {err}", file=sys.stderr)
        return 1


def run_cli_organize(folder_path: str) -> int:
    """Execute organization from the command line."""
    organizer = FileOrganizer()
    path = Path(folder_path).resolve()
    print(f"--- {APP_NAME} v{APP_VERSION} CLI Execution ---")
    print(f"Target Directory: {path}")

    try:
        items, warnings = organizer.preview_organization(path)
        if not items:
            print("No unorganized files found.")
            return 0

        print(f"Found {len(items)} eligible file(s). Organizing...")
        result = organizer.organize_files(path, items)
        categories_count = len({item.category for item in result.moved_items})
        category_word = "category" if categories_count == 1 else "categories"
        print(f"\nResult:")
        if result.moved_count > 0:
            print(f"Successfully organized {result.moved_count} files into {categories_count} {category_word}.")
        else:
            print("No files were moved.")
        if result.skipped_count > 0 or result.error_count > 0:
            print(f" • Skipped: {result.skipped_count}")
            print(f" • Errors:  {result.error_count}")
        if result.errors:
            print("\nErrors encountered:")
            for err in result.errors:
                print(f" [!] {err}")
        return 0 if result.error_count == 0 else 1
    except Exception as err:
        print(f"\nError: {err}", file=sys.stderr)
        return 1


def run_cli_undo(folder_path: str) -> int:
    """Execute undo from the command line."""
    organizer = FileOrganizer()
    path = Path(folder_path).resolve()
    print(f"--- {APP_NAME} v{APP_VERSION} CLI Undo ---")
    print(f"Target Directory: {path}")

    try:
        result = organizer.undo_last_operation(path)
        print(f"\nUndo Result:")
        if result.restored_count > 0:
            print(f"Successfully restored {result.restored_count} files to their original locations.")
        else:
            print("No files were restored.")
        if result.skipped_count > 0 or result.error_count > 0:
            print(f" • Skipped / Unchanged: {result.skipped_count}")
            print(f" • Errors:              {result.error_count}")
        if result.errors:
            print("\nErrors:")
            for err in result.errors:
                print(f" [!] {err}")
        return 0 if result.error_count == 0 else 1
    except Exception as err:
        print(f"\nError: {err}", file=sys.stderr)
        return 1


def launch_gui(initial_dir: str | None = None) -> None:
    """Launch the full graphical Tkinter interface."""
    root = tk.Tk()
    center_window(root, width=1160, height=760)
    app = SmartFileOrganizerGUI(root, initial_dir=initial_dir)

    def on_closing():
        if app.is_busy:
            if not tk.messagebox.askokcancel(
                "Operation in Progress",
                "An operation is currently in progress. Exiting now may interrupt file processing. Close anyway?",
            ):
                return
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


def main() -> None:
    """Parse arguments and start application."""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} - Automatically sort and organize files safely."
    )
    parser.add_argument(
        "--version", "-v", action="version", version=f"{APP_NAME} {APP_VERSION}"
    )
    parser.add_argument(
        "--preview",
        type=str,
        metavar="PATH",
        help="Run a dry-run preview scan on a directory without modifying files.",
    )
    parser.add_argument(
        "--organize",
        type=str,
        metavar="PATH",
        help="Organize files in the specified directory via CLI.",
    )
    parser.add_argument(
        "--undo",
        type=str,
        metavar="PATH",
        help="Undo the last organization operation in the specified directory.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Optional initial directory to open in the GUI.",
    )

    args = parser.parse_args()

    if args.preview:
        sys.exit(run_cli_preview(args.preview))
    elif args.organize:
        sys.exit(run_cli_organize(args.organize))
    elif args.undo:
        sys.exit(run_cli_undo(args.undo))
    else:
        launch_gui(initial_dir=args.directory)


if __name__ == "__main__":
    main()
