"""
Dashboard (Tkinter) - Desktop GUI dashboard for JARVIS-AI.

Displays:
    - Greeting panel with user name and date
    - News panel with top headlines
    - Stock market panel with watched stocks
    - Project progress panel
    - Preferences panel
"""

import threading
import tkinter as tk
from tkinter import ttk


class DashboardModule:
    """
    Tkinter-based desktop dashboard for JARVIS-AI.

    Provides a tabbed interface with panels for different
    information categories. Updates are triggered by events
    from the AI core.
    """

    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config.get("dashboard", {})

        self._running = False
        self._root = None
        self._current_panel = 0

        # Panel data
        self._greeting_text = "Welcome to JARVIS-AI"
        self._news_data = []
        self._stocks_data = {}
        self._project_data = {}

        # Subscribe to events
        self._register_handlers()

    def _register_handlers(self):
        """Register event handlers for dashboard updates."""
        from ai_core.event_bus import EventTypes
        self.event_bus.subscribe(EventTypes.DASHBOARD_UPDATE, self._on_dashboard_update)
        self.event_bus.subscribe(EventTypes.DASHBOARD_SWITCH_PANEL, self._on_switch_panel)
        self.event_bus.subscribe(EventTypes.NEWS_UPDATED, self._on_news_update)
        self.event_bus.subscribe(EventTypes.STOCKS_UPDATED, self._on_stocks_update)
        self.event_bus.subscribe(EventTypes.SPEAK_REQUEST, self._on_speak_request)

    def start(self):
        """Start the dashboard in the main thread."""
        self._running = True
        self._init_ui()
        print("[Dashboard] Started (Tkinter)")

    def stop(self):
        """Stop the dashboard."""
        self._running = False
        if self._root:
            self._root.quit()
        print("[Dashboard] Stopped")

    def _init_ui(self):
        """Initialize the Tkinter UI."""
        self._root = tk.Tk()
        self._root.title("JARVIS-AI Assistant")
        self._root.geometry("800x600")
        self._root.configure(bg="#1a2330")

        # Title bar
        title_frame = tk.Frame(self._root, bg="#1a2330")
        title_frame.pack(fill=tk.X, padx=10, pady=10)

        title_label = tk.Label(
            title_frame,
            text="J.A.R.V.I.S - AI Assistant",
            font=("Helvetica", 18, "bold"),
            fg="#D4875A",
            bg="#1a2330",
        )
        title_label.pack(side=tk.LEFT)

        # Notebook (tabbed interface)
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create panels
        self._create_greeting_panel()
        self._create_news_panel()
        self._create_stocks_panel()
        self._create_project_panel()

        # Status bar
        self._status_var = tk.StringVar(value="Status: Idle")
        status_bar = tk.Label(
            self._root,
            textvariable=self._status_var,
            font=("Helvetica", 10),
            fg="#90989F",
            bg="#1a2330",
            anchor=tk.W,
        )
        status_bar.pack(fill=tk.X, padx=10, pady=5)

        # Start the main loop
        self._root.mainloop()

    def _create_greeting_panel(self):
        """Create the greeting/welcome panel."""
        panel = tk.Frame(self._notebook, bg="#1a2330")
        self._notebook.add(panel, text="Welcome")

        self._greeting_label = tk.Label(
            panel,
            text=self._greeting_text,
            font=("Helvetica", 24, "bold"),
            fg="#FFFFFF",
            bg="#1a2330",
        )
        self._greeting_label.pack(pady=40)

        import datetime
        date_text = datetime.datetime.now().strftime("%A, %B %d, %Y")
        date_label = tk.Label(
            panel,
            text=date_text,
            font=("Helvetica", 14),
            fg="#B0B8C0",
            bg="#1a2330",
        )
        date_label.pack(pady=10)

        # Quick actions
        actions_frame = tk.Frame(panel, bg="#1a2330")
        actions_frame.pack(pady=20)

        actions = ["News", "Stocks", "Project", "Help"]
        for action in actions:
            btn = tk.Button(
                actions_frame,
                text=action,
                font=("Helvetica", 12),
                fg="#FFFFFF",
                bg="#D4875A",
                activebackground="#C0774A",
                width=12,
                height=2,
            )
            btn.pack(side=tk.LEFT, padx=5)

    def _create_news_panel(self):
        """Create the news headlines panel."""
        panel = tk.Frame(self._notebook, bg="#1a2330")
        self._notebook.add(panel, text="News")

        tk.Label(
            panel, text="Today's News Headlines",
            font=("Helvetica", 16, "bold"),
            fg="#FFFFFF", bg="#1a2330",
        ).pack(pady=10)

        self._news_text = tk.Text(
            panel, font=("Helvetica", 11),
            fg="#E0E0E0", bg="#243040",
            wrap=tk.WORD, height=20,
        )
        self._news_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._news_text.insert(tk.END, "Loading news...\n")
        self._news_text.config(state=tk.DISABLED)

    def _create_stocks_panel(self):
        """Create the stock market panel."""
        panel = tk.Frame(self._notebook, bg="#1a2330")
        self._notebook.add(panel, text="Stocks")

        tk.Label(
            panel, text="Stock Market",
            font=("Helvetica", 16, "bold"),
            fg="#FFFFFF", bg="#1a2330",
        ).pack(pady=10)

        self._stocks_text = tk.Text(
            panel, font=("Courier", 12),
            fg="#E0E0E0", bg="#243040",
            wrap=tk.WORD, height=20,
        )
        self._stocks_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._stocks_text.insert(tk.END, "Loading stock data...\n")
        self._stocks_text.config(state=tk.DISABLED)

    def _create_project_panel(self):
        """Create the project progress panel."""
        panel = tk.Frame(self._notebook, bg="#1a2330")
        self._notebook.add(panel, text="Project")

        tk.Label(
            panel, text="Project Progress",
            font=("Helvetica", 16, "bold"),
            fg="#FFFFFF", bg="#1a2330",
        ).pack(pady=10)

        self._project_text = tk.Text(
            panel, font=("Helvetica", 11),
            fg="#E0E0E0", bg="#243040",
            wrap=tk.WORD, height=20,
        )
        self._project_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._project_text.insert(tk.END, "Loading project data...\n")
        self._project_text.config(state=tk.DISABLED)

    # ── Event Handlers ──

    def _on_dashboard_update(self, event):
        """Handle dashboard update event."""
        data = event.data
        if "greeting" in data:
            self._greeting_text = data["greeting"]
            if hasattr(self, "_greeting_label"):
                self._greeting_label.config(text=self._greeting_text)
            self._status_var.set(f"Status: Active - {self._greeting_text}")

    def _on_switch_panel(self, event):
        """Handle panel switch event."""
        data = event.data
        if "panel" in data:
            panel_map = {"news": 1, "stocks": 2, "project": 3}
            panel_idx = panel_map.get(data["panel"], 0)
            self._notebook.select(panel_idx)
        elif "direction" in data and data["direction"] == "next":
            current = self._notebook.index(self._notebook.select())
            next_idx = (current + 1) % self._notebook.index("end")
            self._notebook.select(next_idx)

    def _on_news_update(self, event):
        """Handle news data update."""
        headlines = event.data.get("headlines", [])
        self._news_text.config(state=tk.NORMAL)
        self._news_text.delete("1.0", tk.END)
        for i, headline in enumerate(headlines, 1):
            self._news_text.insert(tk.END, f"{i}. {headline}\n\n")
        self._news_text.config(state=tk.DISABLED)

    def _on_stocks_update(self, event):
        """Handle stock data update."""
        stocks = event.data.get("stocks", {})
        self._stocks_text.config(state=tk.NORMAL)
        self._stocks_text.delete("1.0", tk.END)
        self._stocks_text.insert(tk.END, f"{'Symbol':<8} {'Price':>10} {'Change':>10}\n")
        self._stocks_text.insert(tk.END, "-" * 30 + "\n")
        for symbol, data in stocks.items():
            price = data.get("price", "N/A")
            change = data.get("change", "N/A")
            self._stocks_text.insert(
                tk.END, f"{symbol:<8} {price:>10} {change:>10}\n"
            )
        self._stocks_text.config(state=tk.DISABLED)

    def _on_speak_request(self, event):
        """Handle speak request (display text in status bar)."""
        text = event.data.get("text", "")
        self._status_var.set(f"JARVIS: {text}")
