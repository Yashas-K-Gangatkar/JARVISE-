"""
Data Manager - Central data fetching and caching manager.

Coordinates data retrieval from multiple providers and
publishes data update events to the event bus.
"""

import threading
import time
import json
import os


class DataManager:
    """
    Manages data retrieval from external sources with caching.

    Periodically fetches news, stock, and project data
    and publishes update events.
    """

    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config.get("data", {})
        self._running = False
        self._thread = None
        self._cache = {}
        self._cache_duration = self.config.get("cache_duration_minutes", 30) * 60

    def start(self):
        """Start the data manager."""
        self._running = True
        self._thread = threading.Thread(
            target=self._update_loop, daemon=True, name="DataManager"
        )
        self._thread.start()
        print("[DataManager] Started")

    def stop(self):
        """Stop the data manager."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        print("[DataManager] Stopped")

    def _update_loop(self):
        """Periodically fetch and publish data updates."""
        # Initial fetch
        self._fetch_all()

        # Refresh interval
        refresh_interval = self.config.get("refresh_interval_seconds", 1800)

        while self._running:
            time.sleep(refresh_interval)
            if self._running:
                self._fetch_all()

    def _fetch_all(self):
        """Fetch data from all providers."""
        self._fetch_news()
        self._fetch_stocks()
        self._fetch_project_status()

    def _fetch_news(self):
        """Fetch news headlines from NewsAPI."""
        from ai_core.event_bus import Event, EventTypes

        api_key = self.config.get("news_api_key", "")

        # Detect placeholder keys like "YOUR_NEWSAPI_KEY_HERE"
        if not api_key or api_key.startswith("YOUR_") or "_KEY_HERE" in api_key.upper():
            # Use sample data if no API key
            headlines = [
                "Sample: AI technology advances rapidly in 2026",
                "Sample: Python remains the most popular programming language",
                "Sample: New breakthroughs in computer vision research",
                "Sample: Stock markets show positive trends",
                "Sample: Open source community continues to grow",
            ]
            self.event_bus.publish(
                Event(EventTypes.NEWS_UPDATED, {"headlines": headlines})
            )
            return

        try:
            from .news_provider import NewsProvider
            provider = NewsProvider(api_key)
            headlines = provider.get_headlines(
                categories=self.config.get("news_categories", ["technology"])
            )
            self.event_bus.publish(
                Event(EventTypes.NEWS_UPDATED, {"headlines": headlines})
            )
            print(f"[DataManager] Fetched {len(headlines)} news headlines")
        except Exception as e:
            print(f"[DataManager] News fetch error: {e}")

    def _fetch_stocks(self):
        """Fetch stock market data using yfinance."""
        from ai_core.event_bus import Event, EventTypes

        symbols = self.config.get("stock_symbols", ["AAPL", "GOOGL", "MSFT"])

        try:
            from .stock_provider import StockProvider
            provider = StockProvider()
            stocks = provider.get_stock_data(symbols)
            self.event_bus.publish(
                Event(EventTypes.STOCKS_UPDATED, {"stocks": stocks})
            )
            print(f"[DataManager] Fetched data for {len(stocks)} stocks")
        except Exception as e:
            print(f"[DataManager] Stock fetch error: {e}")
            # Use sample data
            sample_stocks = {symbol: {"price": "N/A", "change": "N/A"} for symbol in symbols}
            self.event_bus.publish(
                Event(EventTypes.STOCKS_UPDATED, {"stocks": sample_stocks})
            )

    def _fetch_project_status(self):
        """Read project status from local JSON file."""
        from ai_core.event_bus import Event, EventTypes

        status_file = self.config.get("project_status_file", "project_status.json")

        if os.path.exists(status_file):
            try:
                with open(status_file, "r") as f:
                    project_data = json.load(f)
                self.event_bus.publish(
                    Event(EventTypes.PROJECT_UPDATED, project_data)
                )
                print("[DataManager] Loaded project status")
            except Exception as e:
                print(f"[DataManager] Project status read error: {e}")
        else:
            print(f"[DataManager] Project status file not found: {status_file}")
