"""Modern Dark-Theme Graphical User Interface for Smart File Organizer.

Faithfully implements the modern dark navy dashboard design from the reference image
using Python's standard library (Tkinter, ttk, Canvas).

Features:
- Dark navy palette with glowing blue/purple accents
- Modern sidebar navigation (Organizer, History, Settings, About)
- Interactive dashboard header with folder selection and validation checkmark
- Four live, dynamic statistics cards (Total Files, Categories, Size, Ready)
- High-contrast action pill buttons (Scan & Preview, Organize Files, Undo)
- Rich file preview table with extension icons, colored categories, and status badges
- Persistent colored status alert banners
- Thread-safe background processing with zero UI freezing
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import datetime
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config import APP_NAME, APP_VERSION, EXTENSION_CATEGORIES, DEFAULT_CATEGORY
from organizer import FileOrganizer, OperationResult, PreviewItem, UndoResult


# ------------------ Color Palette (from Reference Image) ------------------
COLOR_BG_DARK = "#0B0F19"         # Primary dark navy background
COLOR_SIDEBAR_BG = "#080C16"      # Deep sidebar background
COLOR_SIDEBAR_BORDER = "#141A2D"  # Sidebar right divider
COLOR_CARD_BG = "#11162B"         # Standard dashboard card background
COLOR_CARD_BORDER = "#1E2749"     # Card border outline
COLOR_INPUT_BG = "#0A0E1A"        # Inner text input background
COLOR_INPUT_BORDER = "#1E284D"    # Inner input border

# Accents
COLOR_BLUE_PRIMARY = "#2563EB"   # Active blue button & highlights
COLOR_BLUE_HOVER = "#3B82F6"
COLOR_BLUE_BG = "#0F1E38"        # Blue stat card background
COLOR_BLUE_BORDER = "#1D4ED8"    # Blue stat card border

COLOR_PURPLE_PRIMARY = "#7C3AED" # Purple button / category
COLOR_PURPLE_HOVER = "#8B5CF6"
COLOR_PURPLE_BG = "#1C1438"      # Purple stat card background
COLOR_PURPLE_BORDER = "#6D28D9"

COLOR_TEAL_PRIMARY = "#0D9488"   # Teal / Cyan stat card
COLOR_TEAL_BG = "#09212B"
COLOR_TEAL_BORDER = "#0F766E"

COLOR_AMBER_PRIMARY = "#D97706"  # Amber stat card
COLOR_AMBER_BG = "#261A0C"
COLOR_AMBER_BORDER = "#B45309"

COLOR_GREEN_SUCCESS = "#10B981"  # Vibrant green success
COLOR_GREEN_HOVER = "#059669"
COLOR_GREEN_BG = "#062A1F"       # Success banner background
COLOR_GREEN_BORDER = "#059669"

# Text Colors
COLOR_TEXT_PRIMARY = "#F8FAFC"
COLOR_TEXT_SECONDARY = "#94A3B8"
COLOR_TEXT_MUTED = "#64748B"
COLOR_TEXT_DISABLED = "#475569"

# Category Badge Colors (Foreground, Background)
CATEGORY_STYLES = {
    "Archives": ("#D8B4FE", "#3B1866"),      # Light purple on deep purple
    "Audio": ("#F472B6", "#581238"),         # Pink on magenta
    "Code": ("#60A5FA", "#1E3A8A"),          # Light blue on deep blue
    "Documents": ("#93C5FD", "#1E2D5A"),     # Cyan-blue on navy
    "Images": ("#34D399", "#064E3B"),        # Mint green on dark green
    "Presentations": ("#FBBF24", "#5C2B09"), # Gold on dark brown
    "Spreadsheets": ("#2DD4BF", "#0F4A44"),  # Teal on dark teal
    "Videos": ("#F87171", "#521414"),        # Red-coral on dark red
    "Other": ("#94A3B8", "#1E293B"),         # Muted grey on slate
}

# Extension Icon Map
EXTENSION_ICONS = {
    ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".webp": "🖼️", ".bmp": "🖼️",
    ".pdf": "📄", ".doc": "📄", ".docx": "📄", ".txt": "📄", ".rtf": "📄",
    ".csv": "📈", ".xls": "📈", ".xlsx": "📈",
    ".ppt": "📊", ".pptx": "📊",
    ".mp4": "🎬", ".mkv": "🎬", ".avi": "🎬", ".mov": "🎬",
    ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵",
    ".zip": "📦", ".rar": "📦", ".7z": "📦",
    ".py": "💻", ".js": "💻", ".html": "🌐", ".css": "🎨", ".java": "☕", ".cpp": "⚙️",
}


def format_bytes(num_bytes: int) -> str:
    """Format bytes into readable string (e.g. 722 B, 14.5 KB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


class RoundedPillButton(tk.Canvas):
    """Custom pill-shaped modern button built with Tkinter Canvas."""

    def __init__(
        self,
        parent,
        text: str,
        command,
        bg_color: str,
        hover_color: str,
        text_color: str = "#FFFFFF",
        icon: str = "",
        width: int = 150,
        height: int = 40,
        radius: int = 10,
        font=("Segoe UI", 10, "bold"),
        **kwargs,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent.cget("bg") if hasattr(parent, "cget") else COLOR_BG_DARK,
            highlightthickness=0,
            **kwargs,
        )
        self.command = command
        self.text = text
        self.icon = icon
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.btn_width = width
        self.btn_height = height
        self.radius = radius
        self.btn_font = font
        self.is_enabled = True

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

        self._draw(self.bg_color)

    def _draw_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        """Draw smooth rounded rectangle polygon."""
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _draw(self, fill_color: str):
        self.delete("all")
        # Draw body
        self._draw_rounded_rect(
            2, 2, self.btn_width - 2, self.btn_height - 2,
            self.radius,
            fill=fill_color,
            outline="",
        )
        # Content string
        label = f"{self.icon} {self.text}".strip()
        text_col = self.text_color if self.is_enabled else COLOR_TEXT_DISABLED
        self.create_text(
            self.btn_width / 2,
            self.btn_height / 2,
            text=label,
            fill=text_col,
            font=self.btn_font,
        )

    def set_state(self, enabled: bool):
        self.is_enabled = enabled
        if enabled:
            self.configure(cursor="hand2")
            self._draw(self.bg_color)
        else:
            self.configure(cursor="")
            self._draw("#151C30")

    def _on_enter(self, event):
        if self.is_enabled:
            self._draw(self.hover_color)

    def _on_leave(self, event):
        if self.is_enabled:
            self._draw(self.bg_color)

    def _on_click(self, event):
        if self.is_enabled and self.command:
            self.command()


class SmartFileOrganizerGUI:
    """Main application GUI featuring a modern dark-theme dashboard."""

    def __init__(self, root: tk.Tk, initial_dir: Optional[str] = None):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1160x760")
        self.root.minsize(1040, 680)
        self.root.configure(bg=COLOR_BG_DARK)

        # Core file organizer engine
        self.organizer = FileOrganizer()

        # Thread queue for background workers
        self.msg_queue: queue.Queue = queue.Queue()

        # State tracking
        self.selected_directory: Optional[Path] = None
        self.preview_items: List[PreviewItem] = []
        self.is_busy: bool = False
        self.active_tab = "organizer"

        # Setup styling
        self._setup_ttk_styles()

        # Build UI layout
        self._build_layout()

        # Background thread queue processor
        self.root.after(50, self._process_queue)

        # Set initial directory if provided
        if initial_dir and os.path.isdir(initial_dir):
            self.set_directory(initial_dir)

    def _setup_ttk_styles(self):
        """Configure ttk styles for dark theme."""
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        # Treeview styling
        self.style.configure(
            "Treeview",
            background="#0C1021",
            foreground=COLOR_TEXT_PRIMARY,
            fieldbackground="#0C1021",
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            background="#12182D",
            foreground=COLOR_TEXT_SECONDARY,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padding=6,
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", "#18213E")],
            foreground=[("active", COLOR_TEXT_PRIMARY)],
        )
        self.style.map(
            "Treeview",
            background=[("selected", "#1D4ED8")],
            foreground=[("selected", "#FFFFFF")],
        )

        # Scrollbar styling
        self.style.configure(
            "Vertical.TScrollbar",
            background="#151D38",
            troughcolor="#0C1021",
            borderwidth=0,
            arrowcolor=COLOR_TEXT_SECONDARY,
        )

    def _build_layout(self):
        """Assemble the complete layout with sidebar and content area."""
        # Top-level container
        self.container = tk.Frame(self.root, bg=COLOR_BG_DARK)
        self.container.pack(fill=tk.BOTH, expand=True)

        # 1. Left Sidebar
        self._build_sidebar()

        # 2. Main Content Area
        self.main_area = tk.Frame(self.container, bg=COLOR_BG_DARK)
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=16)

        # Views Container (allows switching between Organizer, History, Settings, About)
        self.view_container = tk.Frame(self.main_area, bg=COLOR_BG_DARK)
        self.view_container.pack(fill=tk.BOTH, expand=True)

        # Create Views
        self.views: Dict[str, tk.Frame] = {}
        self._build_organizer_view()
        self._build_history_view()
        self._build_settings_view()
        self._build_about_view()

        # Show Organizer View by default
        self._switch_view("organizer")

    # ------------------ Sidebar Construction ------------------

    def _build_sidebar(self):
        """Construct modern left sidebar matching the reference image."""
        sidebar = tk.Frame(self.container, bg=COLOR_SIDEBAR_BG, width=210)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Right divider line
        divider = tk.Frame(self.container, bg=COLOR_SIDEBAR_BORDER, width=1)
        divider.pack(side=tk.LEFT, fill=tk.Y)

        # 1. Top Logo & Branding
        logo_frame = tk.Frame(sidebar, bg=COLOR_SIDEBAR_BG, pady=20)
        logo_frame.pack(fill=tk.X, padx=16)

        # Folder icon canvas (cyan glowing icon from image)
        icon_canvas = tk.Canvas(logo_frame, width=54, height=44, bg=COLOR_SIDEBAR_BG, highlightthickness=0)
        icon_canvas.pack()
        # Draw blue folder
        icon_canvas.create_polygon(
            6, 12, 22, 12, 28, 18, 48, 18, 48, 38, 6, 38,
            smooth=True, fill="#0284C7", outline=""
        )
        icon_canvas.create_polygon(
            4, 18, 50, 18, 46, 40, 8, 40,
            smooth=True, fill="#38BDF8", outline=""
        )

        title_lbl = tk.Label(
            logo_frame,
            text=APP_NAME,
            font=("Segoe UI", 12, "bold"),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_SIDEBAR_BG,
        )
        title_lbl.pack(pady=(6, 4))

        # Version pill
        ver_pill = tk.Label(
            logo_frame,
            text=f"v{APP_VERSION}",
            font=("Segoe UI", 8, "bold"),
            fg="#93C5FD",
            bg="#16203D",
            padx=8,
            pady=2,
        )
        ver_pill.pack()

        # 2. Navigation Items
        nav_frame = tk.Frame(sidebar, bg=COLOR_SIDEBAR_BG, pady=12)
        nav_frame.pack(fill=tk.X, padx=12)

        self.nav_buttons: Dict[str, tk.Widget] = {}
        nav_items = [
            ("organizer", "🏠  Organizer"),
            ("history", "🕒  History"),
            ("settings", "⚙️  Settings"),
            ("about", "ℹ️  About"),
        ]

        for tab_id, label in nav_items:
            btn = tk.Label(
                nav_frame,
                text=label,
                font=("Segoe UI", 10, "bold" if tab_id == "organizer" else "normal"),
                fg="#FFFFFF" if tab_id == "organizer" else COLOR_TEXT_SECONDARY,
                bg=COLOR_BLUE_PRIMARY if tab_id == "organizer" else COLOR_SIDEBAR_BG,
                anchor="w",
                padx=14,
                pady=9,
                cursor="hand2",
            )
            btn.pack(fill=tk.X, pady=3)
            btn.bind("<Button-1>", lambda e, t=tab_id: self._switch_view(t))
            self.nav_buttons[tab_id] = btn

        # 3. Bottom Decoration Graphic ("Keep Your Files Organized")
        bottom_frame = tk.Frame(sidebar, bg=COLOR_SIDEBAR_BG, pady=16)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12)

        glow_canvas = tk.Canvas(bottom_frame, width=90, height=65, bg=COLOR_SIDEBAR_BG, highlightthickness=0)
        glow_canvas.pack()
        # Draw glowing purple/blue document folder
        glow_canvas.create_oval(15, 45, 75, 62, fill="#3B1866", outline="")
        glow_canvas.create_polygon(
            20, 20, 40, 20, 46, 26, 70, 26, 70, 52, 20, 52,
            smooth=True, fill="#7C3AED", outline=""
        )
        # White paper sticking out
        glow_canvas.create_rectangle(32, 12, 58, 30, fill="#E2E8F0", outline="")
        glow_canvas.create_polygon(
            16, 26, 74, 26, 70, 54, 20, 54,
            smooth=True, fill="#A78BFA", outline=""
        )

        keep_lbl = tk.Label(
            bottom_frame,
            text="Keep Your Files\nOrganized",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_SIDEBAR_BG,
            justify=tk.CENTER,
        )
        keep_lbl.pack(pady=(4, 6))

        # Thin accent bar
        accent_bar = tk.Frame(bottom_frame, bg="#2563EB", height=2, width=32)
        accent_bar.pack()

    def _switch_view(self, tab_id: str):
        """Switch active view between Organizer, History, Settings, About."""
        self.active_tab = tab_id
        for tid, btn in self.nav_buttons.items():
            if tid == tab_id:
                btn.configure(
                    bg=COLOR_BLUE_PRIMARY,
                    fg="#FFFFFF",
                    font=("Segoe UI", 10, "bold"),
                )
            else:
                btn.configure(
                    bg=COLOR_SIDEBAR_BG,
                    fg=COLOR_TEXT_SECONDARY,
                    font=("Segoe UI", 10, "normal"),
                )

        for tid, frame in self.views.items():
            if tid == tab_id:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()

        # Update specific view content if needed
        if tab_id == "history":
            self._refresh_history_view()

    # ------------------ Main Organizer View ------------------

    def _build_organizer_view(self):
        """Construct the core Dashboard matching the reference image."""
        view = tk.Frame(self.view_container, bg=COLOR_BG_DARK)
        self.views["organizer"] = view

        # 1. Dashboard Header
        head_frame = tk.Frame(view, bg=COLOR_BG_DARK)
        head_frame.pack(fill=tk.X, pady=(0, 10))

        # Blue folder icon inside header
        hdr_canvas = tk.Canvas(head_frame, width=44, height=36, bg=COLOR_BG_DARK, highlightthickness=0)
        hdr_canvas.pack(side=tk.LEFT, padx=(0, 10))
        hdr_canvas.create_polygon(
            4, 8, 16, 8, 20, 12, 38, 12, 38, 30, 4, 30,
            smooth=True, fill="#0284C7", outline=""
        )
        hdr_canvas.create_polygon(
            2, 12, 40, 12, 36, 32, 6, 32,
            smooth=True, fill="#38BDF8", outline=""
        )

        title_sub_frame = tk.Frame(head_frame, bg=COLOR_BG_DARK)
        title_sub_frame.pack(side=tk.LEFT, fill=tk.X)

        main_title = tk.Label(
            title_sub_frame,
            text=APP_NAME,
            font=("Segoe UI", 15, "bold"),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK,
        )
        main_title.pack(anchor="w")

        subtitle = tk.Label(
            title_sub_frame,
            text="Automatically organize your files into categorized folders with preview, safe handling, and undo protection.",
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_SECONDARY,
            bg=COLOR_BG_DARK,
        )
        subtitle.pack(anchor="w")

        # 2. Section 1: Select Folder
        sec1_header = tk.Frame(view, bg=COLOR_BG_DARK)
        sec1_header.pack(fill=tk.X, pady=(4, 6))

        # Circle badge '1'
        c1 = tk.Canvas(sec1_header, width=22, height=22, bg=COLOR_BG_DARK, highlightthickness=0)
        c1.pack(side=tk.LEFT, padx=(0, 6))
        c1.create_oval(1, 1, 21, 21, fill=COLOR_BLUE_PRIMARY, outline="")
        c1.create_text(11, 11, text="1", fill="#FFFFFF", font=("Segoe UI", 9, "bold"))

        sec1_title = tk.Label(
            sec1_header,
            text="Select Folder",
            font=("Segoe UI", 11, "bold"),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK,
        )
        sec1_title.pack(side=tk.LEFT)

        # Folder Selection Card
        sel_card = tk.Frame(view, bg=COLOR_CARD_BG, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1)
        sel_card.pack(fill=tk.X, pady=(0, 12))

        sel_inner = tk.Frame(sel_card, bg=COLOR_CARD_BG, padx=12, pady=10)
        sel_inner.pack(fill=tk.X)

        # Input container with path display
        input_box = tk.Frame(sel_inner, bg=COLOR_INPUT_BG, highlightbackground=COLOR_INPUT_BORDER, highlightthickness=1)
        input_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        dir_icon = tk.Label(input_box, text="📁", font=("Segoe UI", 11), fg=COLOR_TEXT_SECONDARY, bg=COLOR_INPUT_BG, padx=8)
        dir_icon.pack(side=tk.LEFT)

        self.dir_var = tk.StringVar(value="Select a folder to organize...")
        self.dir_entry = tk.Entry(
            input_box,
            textvariable=self.dir_var,
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_INPUT_BG,
            relief="flat",
            state="readonly",
            readonlybackground=COLOR_INPUT_BG,
        )
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7)

        # Validation checkmark
        self.valid_icon = tk.Label(input_box, text="", font=("Segoe UI", 11, "bold"), fg=COLOR_GREEN_SUCCESS, bg=COLOR_INPUT_BG, padx=8)
        self.valid_icon.pack(side=tk.RIGHT)

        # Browse Folder Button
        self.browse_btn = RoundedPillButton(
            sel_inner,
            text="Browse Folder",
            command=self._on_browse_directory,
            bg_color="#1D4ED8",
            hover_color=COLOR_BLUE_HOVER,
            icon="📁",
            width=140,
            height=36,
            radius=8,
        )
        self.browse_btn.pack(side=tk.RIGHT)

        # 3. Four Statistics Cards
        stats_frame = tk.Frame(view, bg=COLOR_BG_DARK)
        stats_frame.pack(fill=tk.X, pady=(0, 12))
        stats_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="stat_col")

        self.stat_cards = {}
        stat_configs = [
            ("total_files", "Total Files", "0", "📄", COLOR_BLUE_BG, COLOR_BLUE_BORDER, "#38BDF8"),
            ("categories", "Categories Detected", "0", "📚", COLOR_PURPLE_BG, COLOR_PURPLE_BORDER, "#C084FC"),
            ("total_size", "Total Size", "0 B", "💾", COLOR_TEAL_BG, COLOR_TEAL_BORDER, "#2DD4BF"),
            ("ready_files", "Ready to Organize", "0", "✔", COLOR_AMBER_BG, COLOR_AMBER_BORDER, "#FBBF24"),
        ]

        for idx, (key, title, default_val, icon, bg_col, bdr_col, icon_col) in enumerate(stat_configs):
            card = tk.Frame(stats_frame, bg=bg_col, highlightbackground=bdr_col, highlightthickness=1)
            card.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 6, 0 if idx == 3 else 6))

            c_inner = tk.Frame(card, bg=bg_col, padx=12, pady=10)
            c_inner.pack(fill=tk.BOTH, expand=True)

            # Left square icon badge
            ic_box = tk.Label(
                c_inner,
                text=icon,
                font=("Segoe UI", 14),
                fg=icon_col,
                bg=bdr_col,
                width=3,
                height=1,
            )
            ic_box.pack(side=tk.LEFT, padx=(0, 10))

            # Right numbers and title
            val_lbl = tk.Label(
                c_inner,
                text=default_val,
                font=("Segoe UI", 14, "bold"),
                fg=COLOR_TEXT_PRIMARY,
                bg=bg_col,
                anchor="w",
            )
            val_lbl.pack(anchor="w")

            title_lbl = tk.Label(
                c_inner,
                text=title,
                font=("Segoe UI", 8),
                fg=COLOR_TEXT_SECONDARY,
                bg=bg_col,
                anchor="w",
            )
            title_lbl.pack(anchor="w")

            self.stat_cards[key] = val_lbl

        # 4. Action Buttons Bar
        act_frame = tk.Frame(view, bg=COLOR_BG_DARK)
        act_frame.pack(fill=tk.X, pady=(0, 12))

        self.preview_btn = RoundedPillButton(
            act_frame,
            text="Scan & Preview",
            command=self._on_preview_clicked,
            bg_color=COLOR_BLUE_PRIMARY,
            hover_color=COLOR_BLUE_HOVER,
            icon="🔍",
            width=150,
            height=38,
            radius=8,
        )
        self.preview_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.preview_btn.set_state(False)

        self.organize_btn = RoundedPillButton(
            act_frame,
            text="Organize Files",
            command=self._on_organize_clicked,
            bg_color="#059669",
            hover_color=COLOR_GREEN_SUCCESS,
            icon="▷",
            width=150,
            height=38,
            radius=8,
        )
        self.organize_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.organize_btn.set_state(False)

        self.undo_btn = RoundedPillButton(
            act_frame,
            text="Undo Last Operation",
            command=self._on_undo_clicked,
            bg_color=COLOR_PURPLE_PRIMARY,
            hover_color=COLOR_PURPLE_HOVER,
            icon="↩",
            width=175,
            height=38,
            radius=8,
        )
        self.undo_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.undo_btn.set_state(False)

        # 5. Section 2: Proposed Organization Preview
        sec2_header = tk.Frame(view, bg=COLOR_BG_DARK)
        sec2_header.pack(fill=tk.X, pady=(0, 6))

        # Circle badge '2'
        c2 = tk.Canvas(sec2_header, width=22, height=22, bg=COLOR_BG_DARK, highlightthickness=0)
        c2.pack(side=tk.LEFT, padx=(0, 6))
        c2.create_oval(1, 1, 21, 21, fill=COLOR_BLUE_PRIMARY, outline="")
        c2.create_text(11, 11, text="2", fill="#FFFFFF", font=("Segoe UI", 9, "bold"))

        sec2_title = tk.Label(
            sec2_header,
            text="Proposed Organization Preview",
            font=("Segoe UI", 11, "bold"),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK,
        )
        sec2_title.pack(side=tk.LEFT)

        self.table_summary_label = tk.Label(
            sec2_header,
            text="Total: 0 files | Categories: 0",
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_SECONDARY,
            bg=COLOR_BG_DARK,
        )
        self.table_summary_label.pack(side=tk.RIGHT)

        # 6. Preview Table Card
        table_card = tk.Frame(view, bg=COLOR_CARD_BG, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1)
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("num", "filename", "category", "destination", "size", "status")
        self.tree = ttk.Treeview(
            table_card,
            columns=columns,
            show="headings",
            selectmode="extended",
        )

        self.tree.heading("num", text="#")
        self.tree.heading("filename", text="Original File Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("destination", text="Destination Path")
        self.tree.heading("size", text="Size")
        self.tree.heading("status", text="Status")

        self.tree.column("num", width=45, anchor=tk.CENTER)
        self.tree.column("filename", width=250, anchor=tk.W)
        self.tree.column("category", width=120, anchor=tk.CENTER)
        self.tree.column("destination", width=320, anchor=tk.W)
        self.tree.column("size", width=80, anchor=tk.E)
        self.tree.column("status", width=100, anchor=tk.CENTER)

        # Scrollbars
        vsb = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure category tags for colors
        for cat, (fg_col, bg_col) in CATEGORY_STYLES.items():
            self.tree.tag_configure(f"cat_{cat}", foreground=fg_col)

        self.tree.tag_configure("evenrow", background="#0C1021")
        self.tree.tag_configure("oddrow", background="#11162B")
        self.tree.tag_configure("status_ready", foreground=COLOR_GREEN_SUCCESS)
        self.tree.tag_configure("status_renamed", foreground=COLOR_AMBER_PRIMARY)
        self.tree.tag_configure("status_skipped", foreground=COLOR_TEXT_MUTED)

        # 7. Bottom Notification Banner (Matching Reference Pill)
        self.banner_card = tk.Frame(
            view,
            bg=COLOR_GREEN_BG,
            highlightbackground=COLOR_GREEN_BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        self.banner_card.pack(fill=tk.X)

        self.banner_icon = tk.Label(
            self.banner_card,
            text="✔",
            font=("Segoe UI", 11, "bold"),
            fg=COLOR_GREEN_SUCCESS,
            bg=COLOR_GREEN_BG,
        )
        self.banner_icon.pack(side=tk.LEFT, padx=(0, 8))

        self.banner_text = tk.Label(
            self.banner_card,
            text="Ready. Select a folder to inspect and organize files safely.",
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_GREEN_BG,
            anchor="w",
        )
        self.banner_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ------------------ History View ------------------

    def _build_history_view(self):
        """Construct the History View showing past operation logs."""
        view = tk.Frame(self.view_container, bg=COLOR_BG_DARK)
        self.views["history"] = view

        hdr = tk.Label(
            view,
            text="🕒 Operation History",
            font=("Segoe UI", 15, "bold"),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK,
        )
        hdr.pack(anchor="w", pady=(0, 4))

        sub = tk.Label(
            view,
            text="Review recent file organization operations and active manifests.",
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_SECONDARY,
            bg=COLOR_BG_DARK,
        )
        sub.pack(anchor="w", pady=(0, 14))

        hist_card = tk.Frame(view, bg=COLOR_CARD_BG, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1)
        hist_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        cols = ("time", "folder", "moved", "status")
        self.hist_tree = ttk.Treeview(hist_card, columns=cols, show="headings", selectmode="browse")
        self.hist_tree.heading("time", text="Timestamp")
        self.hist_tree.heading("folder", text="Target Directory")
        self.hist_tree.heading("moved", text="Files Moved")
        self.hist_tree.heading("status", text="Undo Available")

        self.hist_tree.column("time", width=160, anchor=tk.CENTER)
        self.hist_tree.column("folder", width=420, anchor=tk.W)
        self.hist_tree.column("moved", width=100, anchor=tk.CENTER)
        self.hist_tree.column("status", width=120, anchor=tk.CENTER)

        self.hist_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Refresh button
        ref_btn = RoundedPillButton(
            view,
            text="Refresh History",
            command=self._refresh_history_view,
            bg_color=COLOR_BLUE_PRIMARY,
            hover_color=COLOR_BLUE_HOVER,
            icon="🔄",
            width=150,
            height=36,
            radius=8,
        )
        ref_btn.pack(side=tk.LEFT)

    def _refresh_history_view(self):
        """Reload history tree with latest manifest details."""
        for item in self.hist_tree.get_children():
            self.hist_tree.delete(item)

        if self.selected_directory:
            manifest = self.organizer.get_manifest(self.selected_directory)
            if manifest:
                ts = manifest.get("timestamp", "Recent")
                try:
                    dt = datetime.datetime.fromisoformat(ts)
                    ts_display = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ts_display = ts
                self.hist_tree.insert(
                    "",
                    tk.END,
                    values=(
                        ts_display,
                        str(self.selected_directory),
                        f"{manifest.get('total_moved', len(manifest.get('items', [])))} files",
                        "✔ Yes" if manifest.get("items") else "No",
                    ),
                )
                return

        # If no manifest in current directory
        self.hist_tree.insert(
            "",
            tk.END,
            values=("—", "No recent operation manifest found in selected folder", "0", "No"),
        )

    # ------------------ Settings View ------------------

    def _build_settings_view(self):
        """Construct the Settings View displaying supported categories and safety rules."""
        view = tk.Frame(self.view_container, bg=COLOR_BG_DARK)
        self.views["settings"] = view

        hdr = tk.Label(
            view,
            text="⚙️ Supported Categories & Safety Rules",
            font=("Segoe UI", 15, "bold"),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK,
        )
        hdr.pack(anchor="w", pady=(0, 4))

        sub = tk.Label(
            view,
            text="File extensions are automatically matched case-insensitively and sorted into category folders.",
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_SECONDARY,
            bg=COLOR_BG_DARK,
        )
        sub.pack(anchor="w", pady=(0, 14))

        # Categories list card
        cat_card = tk.Frame(view, bg=COLOR_CARD_BG, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1)
        cat_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        cols = ("cat", "extensions")
        cat_tree = ttk.Treeview(cat_card, columns=cols, show="headings", height=9)
        cat_tree.heading("cat", text="Category")
        cat_tree.heading("extensions", text="Supported File Extensions")
        cat_tree.column("cat", width=140, anchor=tk.W)
        cat_tree.column("extensions", width=600, anchor=tk.W)

        for cat, exts in sorted(EXTENSION_CATEGORIES.items()):
            ext_str = ", ".join(sorted(list(exts)))
            cat_tree.insert("", tk.END, values=(cat, ext_str))

        cat_tree.insert("", tk.END, values=(DEFAULT_CATEGORY, "Any unrecognized or extensionless file"))
        cat_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Safety rules info box
        safety_card = tk.Frame(view, bg=COLOR_INPUT_BG, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1, padx=12, pady=10)
        safety_card.pack(fill=tk.X)

        s_title = tk.Label(safety_card, text="🛡️ Built-in Safety Enforcements:", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_INPUT_BG)
        s_title.pack(anchor="w")

        rules = [
            "• Drive roots (C:\\, E:\\) and OS directories (Windows, System32, Program Files) are strictly rejected.",
            "• Subdirectories are skipped in version 1 to protect existing folder trees.",
            "• Symbolic links are never followed or moved.",
            "• Duplicate filenames automatically receive unique incrementing suffixes (_1, _2) to prevent overwrite.",
            "• Files edited after organization are skipped during Undo to prevent data loss.",
        ]
        for r in rules:
            lbl = tk.Label(safety_card, text=r, font=("Segoe UI", 8), fg=COLOR_TEXT_SECONDARY, bg=COLOR_INPUT_BG)
            lbl.pack(anchor="w", pady=1)

    # ------------------ About View ------------------

    def _build_about_view(self):
        """Construct the About View with application info."""
        view = tk.Frame(self.view_container, bg=COLOR_BG_DARK)
        self.views["about"] = view

        hdr = tk.Label(
            view,
            text=f"ℹ️ About {APP_NAME}",
            font=("Segoe UI", 15, "bold"),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK,
        )
        hdr.pack(anchor="w", pady=(0, 4))

        card = tk.Frame(view, bg=COLOR_CARD_BG, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1, padx=16, pady=16)
        card.pack(fill=tk.BOTH, expand=True)

        info_lines = [
            (f"{APP_NAME} v{APP_VERSION}", ("Segoe UI", 12, "bold"), COLOR_TEXT_PRIMARY),
            ("Project #001 of the Daily GitHub Challenge", ("Segoe UI", 10), COLOR_BLUE_HOVER),
            ("\nTechnology Architecture:", ("Segoe UI", 10, "bold"), COLOR_TEXT_PRIMARY),
            ("• Programming Language: Python 3.11+ (Standard Library Only)", ("Segoe UI", 9), COLOR_TEXT_SECONDARY),
            ("• Desktop GUI Framework: Tkinter & ttk with custom Canvas widgets", ("Segoe UI", 9), COLOR_TEXT_SECONDARY),
            ("• Filesystem Engine: pathlib, shutil, os", ("Segoe UI", 9), COLOR_TEXT_SECONDARY),
            ("• Concurrency: Python threading & thread-safe queue.Queue", ("Segoe UI", 9), COLOR_TEXT_SECONDARY),
            ("• Data Integrity: JSON-based reversible operation manifests", ("Segoe UI", 9), COLOR_TEXT_SECONDARY),
            ("\nKey Guarantees:", ("Segoe UI", 10, "bold"), COLOR_TEXT_PRIMARY),
            ("• Zero Overwrites — Duplicates are safely suffixed.", ("Segoe UI", 9), COLOR_TEXT_SECONDARY),
            ("• One-Click Full Undo — Automatically cleans empty category directories.", ("Segoe UI", 9), COLOR_TEXT_SECONDARY),
            ("• Zero External Dependencies — Lightweight, portable, and secure.", ("Segoe UI", 9), COLOR_TEXT_SECONDARY),
        ]

        for text, font_spec, color in info_lines:
            lbl = tk.Label(card, text=text, font=font_spec, fg=color, bg=COLOR_CARD_BG)
            lbl.pack(anchor="w")

    # ------------------ Notification Banner Helper ------------------

    def _set_banner(self, text: str, status: str = "success"):
        """Update the bottom status notification pill."""
        if status == "success":
            bg = COLOR_GREEN_BG
            border = COLOR_GREEN_BORDER
            icon = "✔"
            icon_col = COLOR_GREEN_SUCCESS
        elif status == "info":
            bg = "#0B1E3B"
            border = COLOR_BLUE_BORDER
            icon = "ℹ"
            icon_col = "#38BDF8"
        elif status == "undo":
            bg = "#1F1238"
            border = COLOR_PURPLE_BORDER
            icon = "↩"
            icon_col = "#C084FC"
        elif status == "warning":
            bg = "#291B0B"
            border = COLOR_AMBER_BORDER
            icon = "⚠️"
            icon_col = COLOR_AMBER_PRIMARY
        elif status == "error":
            bg = "#380D0D"
            border = "#991B1B"
            icon = "✕"
            icon_col = "#F87171"
        else:
            bg = COLOR_CARD_BG
            border = COLOR_CARD_BORDER
            icon = "●"
            icon_col = COLOR_TEXT_SECONDARY

        self.banner_card.configure(bg=bg, highlightbackground=border)
        self.banner_icon.configure(text=icon, fg=icon_col, bg=bg)
        self.banner_text.configure(text=text, bg=bg)

    # ------------------ Directory & UI State Logic ------------------

    def set_directory(self, path_str: str) -> None:
        """Set active directory and update UI controls."""
        path = Path(path_str).resolve()
        is_protected, reason = self.organizer.is_protected_directory(path)
        if is_protected:
            self._set_banner(f"Cannot select directory: {reason}", status="error")
            self.valid_icon.configure(text="✕", fg="#F87171")
            messagebox.showerror(
                "Protected Directory Selected",
                f"Cannot select this directory:\n\n{reason}\n\nPlease choose a safe personal folder.",
            )
            return

        self.selected_directory = path
        self.dir_var.set(str(path))
        self.valid_icon.configure(text="✔", fg=COLOR_GREEN_SUCCESS)
        self.preview_items.clear()
        self._clear_tree()

        # Reset stat cards
        self.stat_cards["total_files"].configure(text="0")
        self.stat_cards["categories"].configure(text="0")
        self.stat_cards["total_size"].configure(text="0 B")
        self.stat_cards["ready_files"].configure(text="0")
        self.table_summary_label.configure(text="Total: 0 files | Categories: 0")

        # Check if undo is available
        manifest = self.organizer.get_manifest(path)
        if manifest and manifest.get("items"):
            self.undo_btn.set_state(True)
            self._set_banner(f"Folder selected: '{path.name}'. Previous organization found (Undo available).", status="info")
        else:
            self.undo_btn.set_state(False)
            self._set_banner(f"Folder selected: '{path.name}'. Click 'Scan & Preview' to inspect files.", status="info")

        self.preview_btn.set_state(True)
        self.organize_btn.set_state(False)

    def _on_browse_directory(self) -> None:
        """Handle folder selection dialog."""
        initial = str(self.selected_directory) if self.selected_directory else None
        chosen = filedialog.askdirectory(
            parent=self.root,
            title="Select Folder to Organize",
            initialdir=initial,
        )
        if chosen:
            self.set_directory(chosen)

    def _clear_tree(self) -> None:
        """Clear all rows from the preview table."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _set_ui_busy(self, busy: bool, message: str = ""):
        """Disable or enable buttons during asynchronous operations."""
        self.is_busy = busy
        if busy:
            self.browse_btn.set_state(False)
            self.preview_btn.set_state(False)
            self.organize_btn.set_state(False)
            self.undo_btn.set_state(False)
            if message:
                self._set_banner(message, status="info")
        else:
            self.browse_btn.set_state(True)
            if self.selected_directory:
                self.preview_btn.set_state(True)
                manifest = self.organizer.get_manifest(self.selected_directory)
                self.undo_btn.set_state(bool(manifest and manifest.get("items")))
                self.organize_btn.set_state(bool(self.preview_items))
            if message:
                self._set_banner(message, status="info")

    # ------------------ Asynchronous Workers ------------------

    def _on_preview_clicked(self) -> None:
        """Trigger background directory scan for preview."""
        if not self.selected_directory:
            return
        self._set_ui_busy(True, f"Scanning '{self.selected_directory.name}'...")
        threading.Thread(
            target=self._worker_scan,
            args=(self.selected_directory,),
            daemon=True,
        ).start()

    def _worker_scan(self, directory: Path) -> None:
        """Background thread worker for scanning."""
        try:
            items, warnings = self.organizer.preview_organization(directory)
            self.msg_queue.put(("SCAN_COMPLETE", items, warnings))
        except Exception as err:
            self.msg_queue.put(("SCAN_ERROR", str(err)))

    def _on_organize_clicked(self) -> None:
        """Trigger confirmation dialog and background organization."""
        if not self.selected_directory or not self.preview_items:
            messagebox.showwarning("No Files", "Please run 'Scan & Preview' first.")
            return

        total = len(self.preview_items)
        confirm = messagebox.askyesno(
            "Confirm File Organization",
            f"Are you sure you want to organize {total} file(s) in:\n"
            f"'{self.selected_directory}'?\n\n"
            f"• Category folders will be created automatically.\n"
            f"• Duplicate filenames will be safely renamed.\n"
            f"• No files will be overwritten or deleted.\n"
            f"• You can undo this operation afterwards.",
            icon="question",
        )
        if not confirm:
            return

        self._set_ui_busy(True, "Organizing files into categories...")
        threading.Thread(
            target=self._worker_organize,
            args=(self.selected_directory, self.preview_items),
            daemon=True,
        ).start()

    def _worker_organize(self, directory: Path, items: List[PreviewItem]) -> None:
        """Background thread worker for file organization."""
        def progress(curr: int, tot: int, filename: str) -> None:
            self.msg_queue.put(("ORGANIZE_PROGRESS", curr, tot, filename))

        try:
            result = self.organizer.organize_files(
                directory=directory,
                preview_items=items,
                progress_callback=progress,
            )
            self.msg_queue.put(("ORGANIZE_COMPLETE", result))
        except Exception as err:
            self.msg_queue.put(("ORGANIZE_ERROR", str(err)))

    def _on_undo_clicked(self) -> None:
        """Trigger confirmation dialog and background undo operation."""
        if not self.selected_directory:
            return

        manifest = self.organizer.get_manifest(self.selected_directory)
        if not manifest or not manifest.get("items"):
            messagebox.showinfo("No Undo History", "No recent operation found to undo in this directory.")
            return

        total = len(manifest["items"])
        confirm = messagebox.askyesno(
            "Confirm Undo Operation",
            f"Undo the previous organization of {total} file(s)?\n\n"
            f"• Files will be restored to their original location.\n"
            f"• Modified files and conflicts will be safely skipped.\n"
            f"• Empty category folders will be removed.",
            icon="question",
        )
        if not confirm:
            return

        self._set_ui_busy(True, "Restoring files to original locations...")
        threading.Thread(
            target=self._worker_undo,
            args=(self.selected_directory,),
            daemon=True,
        ).start()

    def _worker_undo(self, directory: Path) -> None:
        """Background thread worker for undoing moves."""
        def progress(curr: int, tot: int, filename: str) -> None:
            self.msg_queue.put(("UNDO_PROGRESS", curr, tot, filename))

        try:
            result = self.organizer.undo_last_operation(
                directory=directory,
                progress_callback=progress,
            )
            self.msg_queue.put(("UNDO_COMPLETE", result))
        except Exception as err:
            self.msg_queue.put(("UNDO_ERROR", str(err)))

    # ------------------ Main Thread Queue Processing ------------------

    def _process_queue(self) -> None:
        """Poll the thread message queue and update GUI widgets safely."""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                msg_type = msg[0]

                if msg_type == "SCAN_COMPLETE":
                    items, warnings = msg[1], msg[2]
                    self._populate_preview(items, warnings)
                    self._set_ui_busy(False)

                elif msg_type == "SCAN_ERROR":
                    err_msg = msg[1]
                    self._set_ui_busy(False)
                    self._set_banner(f"Scan failed: {err_msg}", status="error")
                    messagebox.showerror("Scan Error", f"Failed to scan directory:\n{err_msg}")

                elif msg_type == "ORGANIZE_PROGRESS":
                    curr, tot, filename = msg[1], msg[2], msg[3]
                    self._set_banner(f"Moving ({curr}/{tot}): {filename}", status="info")

                elif msg_type == "ORGANIZE_COMPLETE":
                    result: OperationResult = msg[1]
                    self._on_organize_finished(result)

                elif msg_type == "ORGANIZE_ERROR":
                    err_msg = msg[1]
                    self._set_ui_busy(False)
                    self._set_banner(f"Organization error: {err_msg}", status="error")
                    messagebox.showerror("Organization Error", f"An error occurred:\n{err_msg}")

                elif msg_type == "UNDO_PROGRESS":
                    curr, tot, filename = msg[1], msg[2], msg[3]
                    self._set_banner(f"Restoring ({curr}/{tot}): {filename}", status="undo")

                elif msg_type == "UNDO_COMPLETE":
                    result: UndoResult = msg[1]
                    self._on_undo_finished(result)

                elif msg_type == "UNDO_ERROR":
                    err_msg = msg[1]
                    self._set_ui_busy(False)
                    self._set_banner(f"Undo error: {err_msg}", status="error")
                    messagebox.showerror("Undo Error", f"An error occurred during undo:\n{err_msg}")

                self.msg_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._process_queue)

    def _populate_preview(self, items: List[PreviewItem], warnings: List[str]) -> None:
        """Populate the preview table and update the 4 statistics cards."""
        self.preview_items = items
        self._clear_tree()

        if not items:
            self.stat_cards["total_files"].configure(text="0")
            self.stat_cards["categories"].configure(text="0")
            self.stat_cards["total_size"].configure(text="0 B")
            self.stat_cards["ready_files"].configure(text="0")
            self.table_summary_label.configure(text="Total: 0 files | Categories: 0")
            self._set_banner("Directory is already organized or contains no loose files.", status="info")
            self.organize_btn.set_state(False)
            if warnings:
                messagebox.showwarning("Scan Warnings", "\n".join(warnings[:5]))
            return

        # Compute dynamic metrics
        total_count = len(items)
        categories_set = {item.category for item in items}
        total_size = sum(item.original_size for item in items)
        ready_count = total_count

        self.stat_cards["total_files"].configure(text=str(total_count))
        self.stat_cards["categories"].configure(text=str(len(categories_set)))
        self.stat_cards["total_size"].configure(text=format_bytes(total_size))
        self.stat_cards["ready_files"].configure(text=str(ready_count))

        self.table_summary_label.configure(
            text=f"Total: {total_count} files | Categories: {len(categories_set)}"
        )

        # Populate rows
        for idx, item in enumerate(items, start=1):
            row_tag = "evenrow" if idx % 2 == 0 else "oddrow"
            cat_tag = f"cat_{item.category}"

            # File icon by extension
            ext = Path(item.filename).suffix.lower()
            icon = EXTENSION_ICONS.get(ext, "📄")
            display_name = f"{icon}  {item.filename}"

            rel_dest = str(item.destination_path.name)
            display_dest = f"{item.category}/{rel_dest}"

            status_text = "✔ Ready" if not item.is_duplicate else "⚠️ Renamed"
            status_tag = "status_renamed" if item.is_duplicate else "status_ready"

            self.tree.insert(
                "",
                tk.END,
                values=(
                    idx,
                    display_name,
                    item.category,
                    display_dest,
                    format_bytes(item.original_size),
                    status_text,
                ),
                tags=(row_tag, cat_tag, status_tag),
            )

        # Set success pill banner exactly matching the reference
        banner_msg = f"Preview ready: {total_count} file(s) found across {len(categories_set)} categories. Click \"Organize Files\" to proceed."
        self._set_banner(banner_msg, status="success")
        self.organize_btn.set_state(True)

    def _on_organize_finished(self, result: OperationResult) -> None:
        """Handle organization completion."""
        self.preview_items.clear()
        self._clear_tree()
        self._set_ui_busy(False)

        x_files = result.moved_count
        categories_set = {item.category for item in result.moved_items}
        y_categories = len(categories_set)

        if x_files > 0:
            category_word = "category" if y_categories == 1 else "categories"
            base_msg = f"Successfully organized {x_files} files into {y_categories} {category_word}."
        else:
            base_msg = "No files were moved."

        extra_info = []
        if result.skipped_count > 0:
            extra_info.append(f"{result.skipped_count} skipped")
        if result.error_count > 0:
            extra_info.append(f"{result.error_count} failed")

        if extra_info:
            full_msg = f"{base_msg} ({', '.join(extra_info)})"
        else:
            full_msg = base_msg

        # Update stats
        self.stat_cards["ready_files"].configure(text="0")
        self.table_summary_label.configure(text=f"Organized: {x_files} files | Categories: {y_categories}")

        # Set persistent success banner
        self._set_banner(full_msg, status="success")
        self.undo_btn.set_state(True)

        dialog_lines = [base_msg]
        if result.skipped_count > 0:
            dialog_lines.append(f"• Skipped: {result.skipped_count} file(s)")
        if result.error_count > 0:
            dialog_lines.append(f"• Errors: {result.error_count}")
        if result.errors:
            dialog_lines.append("\nTop Errors:\n" + "\n".join(result.errors[:3]))

        messagebox.showinfo("Organization Complete", "\n".join(dialog_lines))

    def _on_undo_finished(self, result: UndoResult) -> None:
        """Handle undo completion."""
        self._clear_tree()
        self._set_ui_busy(False)

        x_files = result.restored_count
        if x_files > 0:
            base_msg = f"Successfully restored {x_files} files to their original locations."
        else:
            base_msg = "No files were restored."

        extra_info = []
        if result.skipped_count > 0:
            extra_info.append(f"{result.skipped_count} skipped")
        if result.error_count > 0:
            extra_info.append(f"{result.error_count} failed")

        if extra_info:
            full_msg = f"{base_msg} ({', '.join(extra_info)})"
        else:
            full_msg = base_msg

        self._set_banner(full_msg, status="undo")
        self.table_summary_label.configure(text=f"Restored: {x_files} files")

        # Check if any manifest remains
        if self.selected_directory:
            manifest = self.organizer.get_manifest(self.selected_directory)
            self.undo_btn.set_state(bool(manifest and manifest.get("items")))

        dialog_lines = [base_msg]
        if result.skipped_count > 0:
            dialog_lines.append(f"• Skipped / Unchanged: {result.skipped_count} file(s)")
        if result.error_count > 0:
            dialog_lines.append(f"• Errors: {result.error_count}")
        if result.errors:
            dialog_lines.append("\nTop Errors:\n" + "\n".join(result.errors[:3]))

        messagebox.showinfo("Undo Complete", "\n".join(dialog_lines))
