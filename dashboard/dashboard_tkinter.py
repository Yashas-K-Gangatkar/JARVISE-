"""
Dashboard (Tkinter) - Enhanced JARVIS HUD Desktop GUI for JARVIS-AI.

A futuristic, Iron Man-inspired heads-up display with:
    - Animated arc rings and scanning effects
    - Glowing cyan/orange accent theme on dark navy
    - Five tabbed panels: Welcome, News, Stocks, Project, Preferences
    - Live clock, status indicator, and status bar
    - Thread-safe event bus integration

Requires Python 3.8+ and Tkinter (bundled with standard CPython).
"""

import datetime
import math
import threading
import tkinter as tk
from tkinter import ttk, font as tkfont


# ═══════════════════════════════════════════════════════════════════════════════
# Colour Palette
# ═══════════════════════════════════════════════════════════════════════════════
class Colors:
    BG_PRIMARY    = "#0a0e17"
    BG_SECONDARY  = "#131b2e"
    BG_TERTIARY   = "#1a2440"
    BG_CARD       = "#0f1628"
    ACCENT_CYAN   = "#00d4ff"
    ACCENT_ORANGE = "#ff6b35"
    TEXT_PRIMARY   = "#e0e6ed"
    TEXT_MUTED     = "#6b7b8d"
    SUCCESS       = "#00ff88"
    ERROR         = "#ff4444"
    WARNING       = "#ffaa00"
    DIVIDER       = "#1e2d4a"
    GLOW_CYAN     = "#004455"
    GLOW_ORANGE   = "#442200"


# ═══════════════════════════════════════════════════════════════════════════════
# Custom Widgets
# ═══════════════════════════════════════════════════════════════════════════════

class GlowButton(tk.Canvas):
    """A rounded button with a subtle glow border on hover."""

    def __init__(self, parent, text="", command=None, width=140, height=44,
                 bg=Colors.BG_TERTIARY, fg=Colors.ACCENT_CYAN,
                 accent=Colors.ACCENT_CYAN, font_size=11, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=Colors.BG_PRIMARY, highlightthickness=0, **kwargs)
        self._text = text
        self._command = command
        self._bg = bg
        self._fg = fg
        self._accent = accent
        self._font_size = font_size
        self._hover = False
        self._w = width
        self._h = height
        self._r = 8  # corner radius
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw(self):
        self.delete("all")
        pad = 2
        # Glow border (outer)
        glow_col = self._accent if self._hover else Colors.DIVIDER
        self._round_rect(pad, pad, self._w - pad, self._h - pad,
                         self._r, outline=glow_col, width=2)
        # Fill
        fill = Colors.BG_TERTIARY if not self._hover else Colors.BG_SECONDARY
        self._round_rect(pad + 1, pad + 1, self._w - pad - 1, self._h - pad - 1,
                         self._r - 1, fill=fill, outline="")
        # Text
        self.create_text(self._w // 2, self._h // 2, text=self._text,
                         fill=self._fg, font=("Consolas", self._font_size, "bold"))

    def _round_rect(self, x1, y1, x2, y2, r, **kwargs):
        pts = [
            x1 + r, y1, x2 - r, y1,
            x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]
        return self.create_polygon(pts, smooth=True, **kwargs)

    def _on_enter(self, _):
        self._hover = True
        self._draw()

    def _on_leave(self, _):
        self._hover = False
        self._draw()

    def _on_press(self, _):
        self._fg_temp = self._fg
        self._fg = Colors.BG_PRIMARY
        self._draw()

    def _on_release(self, _):
        self._fg = getattr(self, "_fg_temp", self._fg)
        self._draw()
        if self._command:
            self._command()

    def configure_text(self, text):
        self._text = text
        self._draw()


class GlowProgressBar(tk.Canvas):
    """A horizontal progress bar with a glowing fill."""

    def __init__(self, parent, width=400, height=22, progress=0.0,
                 bar_color=Colors.ACCENT_CYAN, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=Colors.BG_PRIMARY, highlightthickness=0, **kwargs)
        self._w = width
        self._h = height
        self._progress = max(0.0, min(1.0, progress))
        self._bar_color = bar_color
        self._r = 6
        self._draw()

    def set_progress(self, progress):
        self._progress = max(0.0, min(1.0, progress))
        self._draw()

    def _draw(self):
        self.delete("all")
        pad = 2
        # Track
        self._round_rect(pad, pad, self._w - pad, self._h - pad,
                         self._r, fill=Colors.BG_TERTIARY, outline=Colors.DIVIDER, width=1)
        # Fill
        fill_w = pad + int((self._w - 2 * pad) * self._progress)
        if fill_w > pad + 2:
            self._round_rect(pad + 1, pad + 1, fill_w, self._h - pad - 1,
                             self._r - 1, fill=self._bar_color, outline="")
            # Glow overlay (semi-transparent simulation via lighter color)
            glow = self._lighten(self._bar_color, 0.35)
            self._round_rect(pad + 1, pad + 1, fill_w, pad + self._h // 3,
                             self._r - 1, fill=glow, outline="")
        # Percentage text
        pct = f"{int(self._progress * 100)}%"
        self.create_text(self._w // 2, self._h // 2, text=pct,
                         fill=Colors.TEXT_PRIMARY, font=("Consolas", 9, "bold"))

    def _round_rect(self, x1, y1, x2, y2, r, **kwargs):
        pts = [
            x1 + r, y1, x2 - r, y1,
            x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]
        return self.create_polygon(pts, smooth=True, **kwargs)

    @staticmethod
    def _lighten(hex_color, factor):
        """Lighten a hex colour by *factor* (0-1)."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"


class HUDArcCanvas(tk.Canvas):
    """Animated arc rings that mimic the Iron Man HUD aesthetic."""

    def __init__(self, parent, width=200, height=200, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=Colors.BG_PRIMARY, highlightthickness=0, **kwargs)
        self._w = width
        self._h = height
        self._cx = width // 2
        self._cy = height // 2
        self._angle_offset = 0.0
        self._running = True
        self._animate()

    def _animate(self):
        if not self._running:
            return
        self._draw_arcs()
        self._angle_offset = (self._angle_offset + 1.2) % 360
        self.after(50, self._animate)

    def _draw_arcs(self):
        self.delete("all")
        cx, cy = self._cx, self._cy
        # Outer ring
        self._draw_ring(cx, cy, 90, self._angle_offset, 290, Colors.ACCENT_CYAN, 2)
        # Middle ring
        self._draw_ring(cx, cy, 70, -self._angle_offset * 0.7, 220, Colors.ACCENT_ORANGE, 1.5)
        # Inner ring
        self._draw_ring(cx, cy, 50, self._angle_offset * 1.5, 150, Colors.ACCENT_CYAN, 1)
        # Centre dot
        self.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                         fill=Colors.ACCENT_CYAN, outline="")

    def _draw_ring(self, cx, cy, radius, start, extent, color, width):
        r = radius
        self.create_arc(cx - r, cy - r, cx + r, cy + r,
                        start=start, extent=extent,
                        style=tk.ARC, outline=color, width=width)

    def stop(self):
        self._running = False


class ScanLineCanvas(tk.Canvas):
    """A subtle horizontal scan-line animation overlay."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=Colors.BG_PRIMARY, highlightthickness=0, **kwargs)
        self._y = 0
        self._running = True
        self._animate()

    def _animate(self):
        if not self._running:
            return
        self.update_idletasks()
        h = self.winfo_height()
        if h > 1:
            self.delete("all")
            # Scan line
            self.create_line(0, self._y, self.winfo_width(), self._y,
                             fill=Colors.GLOW_CYAN, width=1)
            # Faint horizontal guides every 40px
            for gy in range(0, h, 40):
                self.create_line(0, gy, self.winfo_width(), gy,
                                 fill="#0d1a2a", width=1)
            self._y = (self._y + 2) % max(h, 1)
        self.after(60, self._animate)

    def stop(self):
        self._running = False


# ═══════════════════════════════════════════════════════════════════════════════
# Main Dashboard Module
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardModule:
    """
    Tkinter-based JARVIS HUD dashboard for JARVIS-AI.

    Provides a futuristic tabbed interface with animated arcs, glowing
    accent widgets, live clock, and full EventBus integration.

    Usage::
        dashboard = DashboardModule(event_bus, config)
        dashboard.start()   # blocks — must run in main thread
    """

    # Map panel names to tab indices
    _PANEL_MAP = {
        "welcome": 0,
        "news": 1,
        "stocks": 2,
        "project": 3,
        "preferences": 4,
    }

    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config.get("dashboard", {})
        self._preferences_cfg = config.get("preferences", {})
        self._data_cfg = config.get("data", {})

        self._running = False
        self._root = None
        self._current_panel = 0
        self._system_state = "IDLE"

        # Panel data stores
        self._user_name = self._preferences_cfg.get("user_name", "User")
        self._greeting_text = "Welcome to J.A.R.V.I.S."
        self._news_data = []
        self._stocks_data = {}
        self._project_data = {}
        self._preferences_data = self._preferences_cfg

        # Widget references populated during _init_ui
        self._clock_label = None
        self._status_dot = None
        self._status_var = None
        self._greeting_label = None
        self._date_label = None
        self._hud_arc = None
        self._scan_canvas = None
        self._tab_buttons = []
        self._tab_frame = None
        self._news_frame = None
        self._stocks_table = None
        self._project_widgets = {}
        self._prefs_labels = {}

        # Register event handlers
        self._register_handlers()

    # ── Event Registration ──────────────────────────────────────────────────

    def _register_handlers(self):
        from ai_core.event_bus import EventTypes
        self.event_bus.subscribe(EventTypes.DASHBOARD_UPDATE, self._on_dashboard_update)
        self.event_bus.subscribe(EventTypes.DASHBOARD_SWITCH_PANEL, self._on_switch_panel)
        self.event_bus.subscribe(EventTypes.NEWS_UPDATED, self._on_news_update)
        self.event_bus.subscribe(EventTypes.STOCKS_UPDATED, self._on_stocks_update)
        self.event_bus.subscribe(EventTypes.PROJECT_UPDATED, self._on_project_update)
        self.event_bus.subscribe(EventTypes.STATE_CHANGED, self._on_state_change)
        self.event_bus.subscribe(EventTypes.SPEAK_REQUEST, self._on_speak_request)

    # ── Public API ──────────────────────────────────────────────────────────

    def start(self):
        """Start the dashboard — MUST run in the main thread (blocks)."""
        self._running = True
        self._init_ui()
        print("[Dashboard] Started (Tkinter HUD)")

    def stop(self):
        """Stop the dashboard and destroy the window."""
        self._running = False
        if self._hud_arc:
            self._hud_arc.stop()
        if self._scan_canvas:
            self._scan_canvas.stop()
        if self._root:
            try:
                self._root.destroy()
            except tk.TclError:
                pass
        print("[Dashboard] Stopped")

    # ════════════════════════════════════════════════════════════════════════
    # UI Construction
    # ════════════════════════════════════════════════════════════════════════

    def _init_ui(self):
        self._root = tk.Tk()
        self._root.title("J.A.R.V.I.S — AI Assistant")
        self._root.geometry("1100x750")
        self._root.minsize(900, 600)
        self._root.configure(bg=Colors.BG_PRIMARY)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Remove native title bar for cleaner look (optional)
        # self._root.overrideredirect(True)

        # ── Style ttk ──
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Jarvis.TFrame", background=Colors.BG_PRIMARY)
        style.configure("Jarvis.TLabel", background=Colors.BG_PRIMARY,
                        foreground=Colors.TEXT_PRIMARY, font=("Consolas", 11))
        style.configure("Jarvis.TLabelframe", background=Colors.BG_PRIMARY,
                        foreground=Colors.ACCENT_CYAN)
        style.configure("Jarvis.TLabelframe.Label", background=Colors.BG_PRIMARY,
                        foreground=Colors.ACCENT_CYAN, font=("Consolas", 10, "bold"))

        # ── Root grid layout ──
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(1, weight=1)

        # ── Top Header ──
        self._build_header()

        # ── Main Content (tab bar + panels) ──
        self._build_content_area()

        # ── Bottom Status Bar ──
        self._build_status_bar()

        # ── Kick off live clock ──
        self._tick_clock()

        # ── Show default panel ──
        self._switch_to_panel(0)

        # ── Enter main loop ──
        self._root.mainloop()

    # ── Header ──────────────────────────────────────────────────────────────

    def _build_header(self):
        header = tk.Frame(self._root, bg=Colors.BG_SECONDARY, height=60)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.columnconfigure(1, weight=1)

        # Status dot
        self._status_dot = tk.Canvas(header, width=18, height=18,
                                      bg=Colors.BG_SECONDARY, highlightthickness=0)
        self._status_dot.grid(row=0, column=0, padx=(16, 6), pady=16)
        self._draw_status_dot(Colors.ERROR)  # starts idle → red

        # Title with glow layers
        title_frame = tk.Frame(header, bg=Colors.BG_SECONDARY)
        title_frame.grid(row=0, column=1, sticky="w", pady=10)
        # Shadow/glow layer
        tk.Label(title_frame, text="J.A.R.V.I.S",
                 font=("Consolas", 24, "bold"),
                 fg=Colors.GLOW_CYAN, bg=Colors.BG_SECONDARY
                 ).place(x=2, y=2)
        # Main title
        tk.Label(title_frame, text="J.A.R.V.I.S",
                 font=("Consolas", 24, "bold"),
                 fg=Colors.ACCENT_CYAN, bg=Colors.BG_SECONDARY
                 ).pack(side=tk.LEFT)
        tk.Label(title_frame, text="  // AI ASSISTANT",
                 font=("Consolas", 13),
                 fg=Colors.TEXT_MUTED, bg=Colors.BG_SECONDARY
                 ).pack(side=tk.LEFT, padx=(4, 0))

        # Clock
        self._clock_label = tk.Label(header, text="",
                                      font=("Consolas", 14, "bold"),
                                      fg=Colors.ACCENT_ORANGE, bg=Colors.BG_SECONDARY)
        self._clock_label.grid(row=0, column=2, padx=16, pady=10)

        # Divider line
        div = tk.Canvas(self._root, height=2, bg=Colors.BG_PRIMARY, highlightthickness=0)
        div.grid(row=0, column=0, sticky="ew", pady=(60, 0))
        div.create_line(0, 0, 1200, 0, fill=Colors.ACCENT_CYAN, width=1)

    def _draw_status_dot(self, color):
        c = self._status_dot
        c.delete("all")
        # Outer glow
        c.create_oval(2, 2, 16, 16, fill="", outline=color, width=1)
        # Inner fill
        c.create_oval(4, 4, 14, 14, fill=color, outline="")

    # ── Content Area ────────────────────────────────────────────────────────

    def _build_content_area(self):
        content = tk.Frame(self._root, bg=Colors.BG_PRIMARY)
        content.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        content.rowconfigure(1, weight=1)
        content.columnconfigure(0, weight=1)

        # Tab bar
        self._build_tab_bar(content)

        # Panel container
        self._tab_frame = tk.Frame(content, bg=Colors.BG_PRIMARY)
        self._tab_frame.grid(row=1, column=0, sticky="nsew")
        self._tab_frame.rowconfigure(0, weight=1)
        self._tab_frame.columnconfigure(0, weight=1)

        # Build all panels
        self._panels = []
        self._build_welcome_panel()
        self._build_news_panel()
        self._build_stocks_panel()
        self._build_project_panel()
        self._build_preferences_panel()

    # ── Tab Bar ─────────────────────────────────────────────────────────────

    def _build_tab_bar(self, parent):
        bar = tk.Frame(parent, bg=Colors.BG_PRIMARY, height=46)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.columnconfigure(5, weight=1)

        tabs = ["WELCOME", "NEWS", "STOCKS", "PROJECT", "PREFERENCES"]
        self._tab_buttons = []
        for i, name in enumerate(tabs):
            btn = GlowButton(
                bar, text=name, width=130, height=36,
                command=lambda idx=i: self._switch_to_panel(idx),
                fg=Colors.TEXT_MUTED, accent=Colors.ACCENT_CYAN, font_size=10,
            )
            btn.grid(row=0, column=i, padx=(6 if i == 0 else 3, 3), pady=5)
            self._tab_buttons.append(btn)

    def _switch_to_panel(self, index):
        self._current_panel = index
        for i, panel in enumerate(self._panels):
            if i == index:
                panel.grid(row=0, column=0, sticky="nsew")
                self._tab_buttons[i].configure_text(
                    f"▸ {['WELCOME','NEWS','STOCKS','PROJECT','PREFERENCES'][i]}")
                # Highlight active tab
                self._tab_buttons[i]._accent = Colors.ACCENT_CYAN
                self._tab_buttons[i]._fg = Colors.ACCENT_CYAN
            else:
                panel.grid_forget()
                self._tab_buttons[i].configure_text(
                    ['WELCOME', 'NEWS', 'STOCKS', 'PROJECT', 'PREFERENCES'][i])
                self._tab_buttons[i]._accent = Colors.DIVIDER
                self._tab_buttons[i]._fg = Colors.TEXT_MUTED
            self._tab_buttons[i]._draw()

    # ── Welcome Panel ───────────────────────────────────────────────────────

    def _build_welcome_panel(self):
        panel = tk.Frame(self._tab_frame, bg=Colors.BG_PRIMARY)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)
        self._panels.append(panel)

        # Top row: HUD arc + greeting
        top = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        top.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        top.columnconfigure(1, weight=1)

        # HUD arc animation
        self._hud_arc = HUDArcCanvas(top, width=140, height=140)
        self._hud_arc.grid(row=0, column=0, rowspan=2, padx=(0, 20), pady=0)

        # Greeting
        greet_frame = tk.Frame(top, bg=Colors.BG_PRIMARY)
        greet_frame.grid(row=0, column=1, sticky="w")
        self._greeting_label = tk.Label(
            greet_frame, text=self._greeting_text,
            font=("Consolas", 26, "bold"), fg=Colors.ACCENT_CYAN,
            bg=Colors.BG_PRIMARY, anchor="w")
        self._greeting_label.pack(fill=tk.X)

        # User name
        self._user_label = tk.Label(
            greet_frame, text=f"Operator: {self._user_name}",
            font=("Consolas", 13), fg=Colors.ACCENT_ORANGE,
            bg=Colors.BG_PRIMARY, anchor="w")
        self._user_label.pack(fill=tk.X, pady=(4, 0))

        # Date / time
        self._date_label = tk.Label(
            top, text="", font=("Consolas", 12),
            fg=Colors.TEXT_MUTED, bg=Colors.BG_PRIMARY, anchor="w")
        self._date_label.grid(row=1, column=1, sticky="w")

        # Divider
        sep = tk.Canvas(panel, height=2, bg=Colors.BG_PRIMARY, highlightthickness=0)
        sep.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 0))
        sep.create_line(0, 0, 1400, 0, fill=Colors.DIVIDER, width=1)

        # Quick actions
        actions_frame = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        actions_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=16)
        actions_frame.columnconfigure(0, weight=1)

        tk.Label(actions_frame, text="QUICK ACTIONS",
                 font=("Consolas", 12, "bold"), fg=Colors.TEXT_MUTED,
                 bg=Colors.BG_PRIMARY, anchor="w").grid(row=0, column=0, sticky="w")

        btn_frame = tk.Frame(actions_frame, bg=Colors.BG_PRIMARY)
        btn_frame.grid(row=1, column=0, sticky="w", pady=(10, 0))

        quick_actions = [
            ("📰  Show News", self._cmd_news),
            ("📈  Show Stocks", self._cmd_stocks),
            ("📊  Project Status", self._cmd_project),
            ("⚙  Preferences", self._cmd_preferences),
            ("🔄  Refresh Data", self._cmd_refresh),
        ]
        for i, (label, cmd) in enumerate(quick_actions):
            accent = Colors.ACCENT_CYAN if i % 2 == 0 else Colors.ACCENT_ORANGE
            btn = GlowButton(btn_frame, text=label, command=cmd,
                             width=160, height=42, accent=accent,
                             fg=accent, font_size=10)
            btn.grid(row=0, column=i, padx=6)

        # System info card
        info_frame = tk.Frame(actions_frame, bg=Colors.BG_CARD,
                               highlightbackground=Colors.DIVIDER,
                               highlightthickness=1)
        info_frame.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        info_frame.columnconfigure(1, weight=1)

        tk.Label(info_frame, text="SYSTEM STATUS",
                 font=("Consolas", 11, "bold"), fg=Colors.ACCENT_CYAN,
                 bg=Colors.BG_CARD).grid(row=0, column=0, columnspan=2,
                                          sticky="w", padx=16, pady=(12, 4))
        info_items = [
            ("Core Engine", "ONLINE", Colors.SUCCESS),
            ("Voice Module", "STANDBY", Colors.WARNING),
            ("Face Recognition", "STANDBY", Colors.WARNING),
            ("Gesture Control", "STANDBY", Colors.WARNING),
            ("Data Services", "ONLINE", Colors.SUCCESS),
        ]
        for i, (key, val, col) in enumerate(info_items):
            tk.Label(info_frame, text=f"  {key}",
                     font=("Consolas", 10), fg=Colors.TEXT_MUTED,
                     bg=Colors.BG_CARD, anchor="w"
                     ).grid(row=i + 1, column=0, sticky="w", padx=(16, 0))
            tk.Label(info_frame, text=val,
                     font=("Consolas", 10, "bold"), fg=col,
                     bg=Colors.BG_CARD, anchor="e"
                     ).grid(row=i + 1, column=1, sticky="e", padx=(0, 16))
        # Bottom padding
        tk.Frame(info_frame, bg=Colors.BG_CARD, height=10).grid(
            row=len(info_items) + 1, column=0, columnspan=2)

    # ── News Panel ──────────────────────────────────────────────────────────

    def _build_news_panel(self):
        panel = tk.Frame(self._tab_frame, bg=Colors.BG_PRIMARY)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        self._panels.append(panel)

        # Header
        hdr = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        tk.Label(hdr, text="📰  NEWS HEADLINES",
                 font=("Consolas", 16, "bold"), fg=Colors.ACCENT_CYAN,
                 bg=Colors.BG_PRIMARY).pack(side=tk.LEFT)
        tk.Label(hdr, text=f"  Categories: {', '.join(self._preferences_cfg.get('news_categories', ['technology']))}",
                 font=("Consolas", 10), fg=Colors.TEXT_MUTED,
                 bg=Colors.BG_PRIMARY).pack(side=tk.LEFT, padx=12)

        # Scrollable frame
        container = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        container.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container, bg=Colors.BG_PRIMARY, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        self._news_frame = tk.Frame(canvas, bg=Colors.BG_PRIMARY)

        self._news_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._news_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Populate placeholder
        self._render_news([])

    def _render_news(self, headlines):
        for w in self._news_frame.winfo_children():
            w.destroy()
        if not headlines:
            headlines = ["Awaiting news feed..."]
        for i, hl in enumerate(headlines):
            row = tk.Frame(self._news_frame, bg=Colors.BG_CARD,
                           highlightbackground=Colors.DIVIDER,
                           highlightthickness=1)
            row.pack(fill=tk.X, pady=3, padx=4)

            # Index badge
            idx_lbl = tk.Label(row, text=f" {i + 1:02d} ",
                               font=("Consolas", 12, "bold"),
                               fg=Colors.BG_PRIMARY, bg=Colors.ACCENT_CYAN, width=4)
            idx_lbl.pack(side=tk.LEFT, padx=(6, 10), pady=8)

            # Headline
            tk.Label(row, text=hl, font=("Consolas", 11),
                     fg=Colors.TEXT_PRIMARY, bg=Colors.BG_CARD,
                     wraplength=700, justify=tk.LEFT, anchor="w"
                     ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12), pady=8)

    # ── Stocks Panel ────────────────────────────────────────────────────────

    def _build_stocks_panel(self):
        panel = tk.Frame(self._tab_frame, bg=Colors.BG_PRIMARY)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        self._panels.append(panel)

        # Header
        hdr = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        tk.Label(hdr, text="📈  STOCK MARKET",
                 font=("Consolas", 16, "bold"), fg=Colors.ACCENT_CYAN,
                 bg=Colors.BG_PRIMARY).pack(side=tk.LEFT)
        watchlist = self._data_cfg.get("stock_symbols", ["AAPL", "GOOGL", "MSFT"])
        tk.Label(hdr, text=f"  Watchlist: {', '.join(watchlist)}",
                 font=("Consolas", 10), fg=Colors.TEXT_MUTED,
                 bg=Colors.BG_PRIMARY).pack(side=tk.LEFT, padx=12)

        # Table container
        table_frame = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=1)

        # Column headers
        header_row = tk.Frame(table_frame, bg=Colors.BG_SECONDARY)
        header_row.grid(row=0, column=0, sticky="ew")
        cols = [("SYMBOL", 100), ("COMPANY", 220), ("PRICE", 120),
                ("CHANGE", 120), ("CHANGE %", 120), ("STATUS", 100)]
        for col_name, col_w in cols:
            tk.Label(header_row, text=col_name, font=("Consolas", 10, "bold"),
                     fg=Colors.ACCENT_CYAN, bg=Colors.BG_SECONDARY,
                     width=col_w // 10, anchor="w"
                     ).pack(side=tk.LEFT, padx=8, pady=8)

        # Scrollable body
        body_canvas = tk.Canvas(table_frame, bg=Colors.BG_PRIMARY, highlightthickness=0)
        body_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=body_canvas.yview)
        self._stocks_table = tk.Frame(body_canvas, bg=Colors.BG_PRIMARY)
        self._stocks_table.bind(
            "<Configure>",
            lambda e: body_canvas.configure(scrollregion=body_canvas.bbox("all")))
        body_canvas.create_window((0, 0), window=self._stocks_table, anchor="nw")
        body_canvas.configure(yscrollcommand=body_scroll.set)
        body_canvas.grid(row=1, column=0, sticky="nsew")
        body_scroll.grid(row=1, column=1, sticky="ns")

        # Placeholder
        self._render_stocks({})

    def _render_stocks(self, stocks):
        for w in self._stocks_table.winfo_children():
            w.destroy()
        if not stocks:
            # Placeholder rows
            for sym in self._data_cfg.get("stock_symbols", ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]):
                self._add_stock_row(sym, "—", "—", "—", Colors.TEXT_MUTED)
            return
        for symbol, data in stocks.items():
            price = data.get("price", "N/A")
            change = data.get("change", "N/A")
            change_pct = data.get("change_pct", "N/A")
            # Determine colour based on change
            try:
                ch = float(str(change).replace("+", ""))
                color = Colors.SUCCESS if ch >= 0 else Colors.ERROR
            except (ValueError, TypeError):
                color = Colors.TEXT_MUTED
            self._add_stock_row(symbol, "", price, change, color, change_pct)

    def _add_stock_row(self, symbol, company, price, change, color, change_pct=""):
        row = tk.Frame(self._stocks_table, bg=Colors.BG_CARD,
                       highlightbackground=Colors.DIVIDER, highlightthickness=1)
        row.pack(fill=tk.X, pady=2, padx=2)
        fields = [
            (symbol, Colors.ACCENT_CYAN, 10),
            (company, Colors.TEXT_MUTED, 22),
            (str(price), Colors.TEXT_PRIMARY, 12),
            (str(change), color, 12),
            (str(change_pct), color, 12),
            ("●", color, 10),
        ]
        for text, fg, w in fields:
            tk.Label(row, text=text, font=("Consolas", 10),
                     fg=fg, bg=Colors.BG_CARD, width=w, anchor="w"
                     ).pack(side=tk.LEFT, padx=8, pady=6)

    # ── Project Panel ───────────────────────────────────────────────────────

    def _build_project_panel(self):
        panel = tk.Frame(self._tab_frame, bg=Colors.BG_PRIMARY)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)
        self._panels.append(panel)

        # Header
        hdr = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        tk.Label(hdr, text="📊  PROJECT PROGRESS",
                 font=("Consolas", 16, "bold"), fg=Colors.ACCENT_CYAN,
                 bg=Colors.BG_PRIMARY).pack(side=tk.LEFT)

        # Overall progress
        overall_frame = tk.Frame(panel, bg=Colors.BG_CARD,
                                  highlightbackground=Colors.DIVIDER,
                                  highlightthickness=1)
        overall_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 0))
        overall_frame.columnconfigure(1, weight=1)

        tk.Label(overall_frame, text="  OVERALL PROGRESS",
                 font=("Consolas", 11, "bold"), fg=Colors.ACCENT_ORANGE,
                 bg=Colors.BG_CARD).grid(row=0, column=0, sticky="w", padx=8, pady=(10, 4))

        self._project_overall_bar = GlowProgressBar(
            overall_frame, width=500, height=26, progress=0.1,
            bar_color=Colors.ACCENT_ORANGE)
        self._project_overall_bar.grid(row=0, column=1, sticky="ew", padx=16, pady=(10, 4))

        self._project_overall_label = tk.Label(
            overall_frame, text="10%", font=("Consolas", 14, "bold"),
            fg=Colors.ACCENT_ORANGE, bg=Colors.BG_CARD)
        self._project_overall_label.grid(row=0, column=2, padx=(8, 16), pady=(10, 4))

        # Milestones container
        self._milestones_frame = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        self._milestones_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=12)
        self._milestones_frame.columnconfigure(0, weight=1)

        self._render_project({})

    def _render_project(self, data):
        for w in self._milestones_frame.winfo_children():
            w.destroy()

        if not data:
            # Default placeholder
            data = {
                "project_name": "JARVIS-AI",
                "overall_progress": 10,
                "status": "In Development",
                "milestones": [
                    {"name": "Phase 1: Setup & Learning", "status": "In Progress", "progress": 50},
                    {"name": "Phase 2: Core Module Development", "status": "Not Started", "progress": 0},
                    {"name": "Phase 3: Integration & Testing", "status": "Not Started", "progress": 0},
                    {"name": "Phase 4: Polish & Documentation", "status": "Not Started", "progress": 0},
                ],
            }

        # Update overall bar
        overall = data.get("overall_progress", 0) / 100.0
        self._project_overall_bar.set_progress(overall)
        self._project_overall_label.config(text=f"{data.get('overall_progress', 0)}%")

        # Status badge
        status = data.get("status", "Unknown")
        status_color = Colors.SUCCESS if "progress" in status.lower() else Colors.WARNING
        status_lbl = tk.Label(self._milestones_frame,
                              text=f"  Status: {status}  ",
                              font=("Consolas", 11, "bold"), fg=status_color,
                              bg=Colors.BG_CARD, anchor="w")
        status_lbl.pack(fill=tk.X, pady=(0, 8))

        # Milestones
        tk.Label(self._milestones_frame, text="MILESTONES",
                 font=("Consolas", 11, "bold"), fg=Colors.TEXT_MUTED,
                 bg=Colors.BG_PRIMARY, anchor="w").pack(fill=tk.X, pady=(4, 4))

        for ms in data.get("milestones", []):
            card = tk.Frame(self._milestones_frame, bg=Colors.BG_CARD,
                            highlightbackground=Colors.DIVIDER, highlightthickness=1)
            card.pack(fill=tk.X, pady=3)

            top_row = tk.Frame(card, bg=Colors.BG_CARD)
            top_row.pack(fill=tk.X, padx=12, pady=(8, 2))
            top_row.columnconfigure(1, weight=1)

            name = ms.get("name", "Unknown")
            ms_status = ms.get("status", "Unknown")
            progress = ms.get("progress", 0)

            st_color = Colors.SUCCESS if "progress" in ms_status.lower() or "complete" in ms_status.lower() else (
                Colors.WARNING if "not" not in ms_status.lower() else Colors.TEXT_MUTED)
            tk.Label(top_row, text=name, font=("Consolas", 10, "bold"),
                     fg=Colors.TEXT_PRIMARY, bg=Colors.BG_CARD, anchor="w"
                     ).grid(row=0, column=0, sticky="w")
            tk.Label(top_row, text=ms_status, font=("Consolas", 9),
                     fg=st_color, bg=Colors.BG_CARD, anchor="e"
                     ).grid(row=0, column=1, sticky="e")

            bar = GlowProgressBar(card, width=400, height=18, progress=progress / 100.0,
                                  bar_color=st_color)
            bar.pack(fill=tk.X, padx=12, pady=(2, 8))

    # ── Preferences Panel ───────────────────────────────────────────────────

    def _build_preferences_panel(self):
        panel = tk.Frame(self._tab_frame, bg=Colors.BG_PRIMARY)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        self._panels.append(panel)

        # Header
        hdr = tk.Frame(panel, bg=Colors.BG_PRIMARY)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        tk.Label(hdr, text="⚙  USER PREFERENCES",
                 font=("Consolas", 16, "bold"), fg=Colors.ACCENT_CYAN,
                 bg=Colors.BG_PRIMARY).pack(side=tk.LEFT)

        # Preferences card
        card = tk.Frame(panel, bg=Colors.BG_CARD,
                         highlightbackground=Colors.DIVIDER, highlightthickness=1)
        card.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        card.columnconfigure(1, weight=1)

        defaults = {
            "user_name": "User",
            "news_categories": ["technology", "business", "science"],
            "stock_watchlist": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
            "greeting_style": "formal",
            "voice_speed": "normal",
            "dashboard_default_panel": "greeting",
        }
        prefs = {**defaults, **self._preferences_data}

        row = 0
        self._prefs_labels = {}
        for key, value in prefs.items():
            # Key
            tk.Label(card, text=f"  {key.upper().replace('_', ' ')}",
                     font=("Consolas", 10), fg=Colors.TEXT_MUTED,
                     bg=Colors.BG_CARD, anchor="w"
                     ).grid(row=row, column=0, sticky="w", padx=(12, 8), pady=6)

            # Value
            if isinstance(value, list):
                val_text = ", ".join(str(v) for v in value)
            else:
                val_text = str(value)
            lbl = tk.Label(card, text=val_text,
                           font=("Consolas", 10, "bold"), fg=Colors.ACCENT_CYAN,
                           bg=Colors.BG_CARD, anchor="w", wraplength=500)
            lbl.grid(row=row, column=1, sticky="w", padx=(8, 12), pady=6)
            self._prefs_labels[key] = lbl

            row += 1

    # ── Status Bar ──────────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = tk.Frame(self._root, bg=Colors.BG_SECONDARY, height=32)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.columnconfigure(1, weight=1)

        # Indicator
        tk.Label(bar, text="  ◆", font=("Consolas", 10),
                 fg=Colors.ACCENT_CYAN, bg=Colors.BG_SECONDARY
                 ).grid(row=0, column=0, padx=(8, 0))

        self._status_var = tk.StringVar(value="JARVIS: System idle. Awaiting input.")
        tk.Label(bar, textvariable=self._status_var,
                 font=("Consolas", 10), fg=Colors.TEXT_MUTED,
                 bg=Colors.BG_SECONDARY, anchor="w"
                 ).grid(row=0, column=1, sticky="w", padx=(4, 0))

        # State badge
        self._state_badge = tk.Label(bar, text=" IDLE ",
                                      font=("Consolas", 9, "bold"),
                                      fg=Colors.ERROR, bg=Colors.BG_SECONDARY)
        self._state_badge.grid(row=0, column=2, padx=(0, 12))

    # ════════════════════════════════════════════════════════════════════════
    # Live Clock
    # ════════════════════════════════════════════════════════════════════════

    def _tick_clock(self):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%A, %B %d, %Y")
        if self._clock_label:
            self._clock_label.config(text=time_str)
        if self._date_label:
            self._date_label.config(text=f"{date_str}  •  {time_str}")
        if self._root:
            self._root.after(1000, self._tick_clock)

    # ════════════════════════════════════════════════════════════════════════
    # Quick-action Commands (publish events)
    # ════════════════════════════════════════════════════════════════════════

    def _cmd_news(self):
        from ai_core.event_bus import Event, EventTypes
        self.event_bus.publish(Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "news"}))
        self.event_bus.publish(Event(EventTypes.SPEAK_REQUEST, {"text": "Switching to news panel."}))

    def _cmd_stocks(self):
        from ai_core.event_bus import Event, EventTypes
        self.event_bus.publish(Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "stocks"}))
        self.event_bus.publish(Event(EventTypes.SPEAK_REQUEST, {"text": "Switching to stocks panel."}))

    def _cmd_project(self):
        from ai_core.event_bus import Event, EventTypes
        self.event_bus.publish(Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "project"}))
        self.event_bus.publish(Event(EventTypes.SPEAK_REQUEST, {"text": "Switching to project panel."}))

    def _cmd_preferences(self):
        from ai_core.event_bus import Event, EventTypes
        self.event_bus.publish(Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "preferences"}))
        self.event_bus.publish(Event(EventTypes.SPEAK_REQUEST, {"text": "Switching to preferences panel."}))

    def _cmd_refresh(self):
        from ai_core.event_bus import Event, EventTypes
        self.event_bus.publish(Event(EventTypes.SPEAK_REQUEST, {"text": "Refreshing all data sources."}))
        self._status_var.set("JARVIS: Refreshing all data sources...")

    # ════════════════════════════════════════════════════════════════════════
    # Event Handlers (thread-safe via root.after)
    # ════════════════════════════════════════════════════════════════════════

    def _on_dashboard_update(self, event):
        """Handle DASHBOARD_UPDATE — update greeting, preferences, etc."""
        data = event.data
        self._root.after(0, self._apply_dashboard_update, data)

    def _apply_dashboard_update(self, data):
        if "greeting" in data:
            self._greeting_text = data["greeting"]
            if self._greeting_label:
                self._greeting_label.config(text=self._greeting_text)
            self._status_var.set(f"JARVIS: {self._greeting_text}")
        if "user_name" in data:
            self._user_name = data["user_name"]
            if self._user_label:
                self._user_label.config(text=f"Operator: {self._user_name}")
        if data.get("show_preferences") and self._preferences_data:
            self._update_prefs_display()

    def _on_switch_panel(self, event):
        """Handle DASHBOARD_SWITCH_PANEL."""
        data = event.data
        self._root.after(0, self._apply_switch_panel, data)

    def _apply_switch_panel(self, data):
        if "panel" in data:
            idx = self._PANEL_MAP.get(data["panel"], 0)
            self._switch_to_panel(idx)
        elif "direction" in data:
            direction = data["direction"]
            if direction == "next":
                idx = (self._current_panel + 1) % len(self._panels)
            elif direction == "prev":
                idx = (self._current_panel - 1) % len(self._panels)
            else:
                idx = self._current_panel
            self._switch_to_panel(idx)

    def _on_news_update(self, event):
        """Handle NEWS_UPDATED."""
        headlines = event.data.get("headlines", [])
        self._news_data = headlines
        self._root.after(0, self._render_news, headlines)

    def _on_stocks_update(self, event):
        """Handle STOCKS_UPDATED."""
        stocks = event.data.get("stocks", {})
        self._stocks_data = stocks
        self._root.after(0, self._render_stocks, stocks)

    def _on_project_update(self, event):
        """Handle PROJECT_UPDATED."""
        data = event.data
        self._project_data = data
        self._root.after(0, self._render_project, data)

    def _on_state_change(self, event):
        """Handle STATE_CHANGED — update status dot and badge."""
        state = event.data.get("state", "IDLE")
        self._system_state = state
        self._root.after(0, self._apply_state_change, state)

    def _apply_state_change(self, state):
        if state in ("ACTIVE", "LISTENING", "PROCESSING"):
            self._draw_status_dot(Colors.SUCCESS)
            self._state_badge.config(text=f" {state} ", fg=Colors.SUCCESS)
        elif state == "ERROR":
            self._draw_status_dot(Colors.ERROR)
            self._state_badge.config(text=" ERROR ", fg=Colors.ERROR)
        else:
            self._draw_status_dot(Colors.ERROR)
            self._state_badge.config(text=" IDLE ", fg=Colors.ERROR)

    def _on_speak_request(self, event):
        """Handle SPEAK_REQUEST — show text in status bar."""
        text = event.data.get("text", "")
        self._root.after(0, self._apply_speak, text)

    def _apply_speak(self, text):
        self._status_var.set(f"JARVIS: {text}")

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _update_prefs_display(self):
        """Refresh the preferences panel labels."""
        for key, lbl in self._prefs_labels.items():
            val = self._preferences_data.get(key, "—")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            lbl.config(text=str(val))

    def _on_close(self):
        """Handle window close."""
        self.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone Test Mode
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """Run the dashboard standalone with a mock event bus for testing."""

    class _MockEventBus:
        """Minimal event bus stub that prints published events."""
        def __init__(self):
            self._subs = {}

        def subscribe(self, event_type, callback):
            self._subs.setdefault(event_type, []).append(callback)

        def publish(self, event):
            print(f"  [MockBus] Published: {event}")
            for cb in self._subs.get(event.event_type, []):
                try:
                    cb(event)
                except Exception as exc:
                    print(f"  [MockBus] Error in callback: {exc}")

        def start_processing(self):
            pass

        def stop_processing(self):
            pass

    config = {
        "dashboard": {"type": "tkinter", "refresh_interval_seconds": 30},
        "preferences": {
            "user_name": "Operator",
            "news_categories": ["technology", "business", "science"],
            "greeting_style": "formal",
            "voice_speed": "normal",
            "dashboard_default_panel": "greeting",
        },
        "data": {
            "stock_symbols": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
            "project_status_file": "project_status.json",
        },
    }

    bus = _MockEventBus()
    dashboard = DashboardModule(bus, config)

    # Schedule some demo events after the window opens
    def _demo_events():
        import time
        time.sleep(2)

        from ai_core.event_bus import Event, EventTypes

        # Greeting
        bus.publish(Event(EventTypes.DASHBOARD_UPDATE, {
            "greeting": "Good Evening, Operator!",
            "user_name": "Operator",
        }))

        # State change
        bus.publish(Event(EventTypes.STATE_CHANGED, {"state": "ACTIVE"}))

        # Speak
        bus.publish(Event(EventTypes.SPEAK_REQUEST, {
            "text": "All systems operational. How may I assist you?"
        }))

        time.sleep(3)

        # News
        bus.publish(Event(EventTypes.NEWS_UPDATED, {
            "headlines": [
                "OpenAI announces GPT-5 with multimodal reasoning",
                "Tesla stock surges on record Q4 deliveries",
                "NASA confirms water ice deposits on the Moon's south pole",
                "Apple Vision Pro 2 leak reveals lighter design",
                "EU passes landmark AI regulation framework",
                "Quantum computing breakthrough: 1000-qubit processor demonstrated",
                "SpaceX Starship completes first orbital refueling test",
            ]
        }))

        time.sleep(2)

        # Stocks
        bus.publish(Event(EventTypes.STOCKS_UPDATED, {
            "stocks": {
                "AAPL": {"price": "$213.45", "change": "+2.31", "change_pct": "+1.09%"},
                "GOOGL": {"price": "$178.92", "change": "-0.87", "change_pct": "-0.48%"},
                "MSFT": {"price": "$445.20", "change": "+5.64", "change_pct": "+1.28%"},
                "AMZN": {"price": "$198.33", "change": "+1.45", "change_pct": "+0.74%"},
                "TSLA": {"price": "$267.11", "change": "+12.08", "change_pct": "+4.74%"},
            }
        }))

        time.sleep(2)

        # Project
        bus.publish(Event(EventTypes.PROJECT_UPDATED, {
            "project_name": "JARVIS-AI",
            "overall_progress": 18,
            "status": "In Development",
            "milestones": [
                {"name": "Phase 1: Setup & Learning", "status": "In Progress", "progress": 65},
                {"name": "Phase 2: Core Module Development", "status": "Starting", "progress": 10},
                {"name": "Phase 3: Integration & Testing", "status": "Not Started", "progress": 0},
                {"name": "Phase 4: Polish & Documentation", "status": "Not Started", "progress": 0},
            ],
        }))

        time.sleep(3)

        # Switch panel
        bus.publish(Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "news"}))

    demo_thread = threading.Thread(target=_demo_events, daemon=True)
    demo_thread.start()

    dashboard.start()
