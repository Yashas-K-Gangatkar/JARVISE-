"""
News Provider - Fetches news headlines from NewsAPI or RSS feeds.
"""

import requests


class NewsProvider:
    """
    Provides news headline data from NewsAPI.org.

    Falls back to RSS feed parsing if API is unavailable.
    """

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, api_key):
        self.api_key = api_key

    def get_headlines(self, country="us", categories=None, page_size=10):
        """
        Fetch top news headlines.

        Args:
            country: Country code (default: "us")
            categories: List of categories to filter
            page_size: Number of headlines to return

        Returns:
            list: List of headline strings
        """
        params = {
            "apiKey": self.api_key,
            "country": country,
            "pageSize": page_size,
        }

        if categories:
            # NewsAPI supports one category at a time
            params["category"] = categories[0]

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            headlines = []
            for article in data.get("articles", []):
                title = article.get("title", "No title")
                source = article.get("source", {}).get("name", "Unknown")
                headlines.append(f"[{source}] {title}")

            return headlines

        except requests.RequestException as e:
            print(f"[NewsProvider] API error: {e}")
            return self._fallback_rss()

    def _fallback_rss(self):
        """Fallback: Parse RSS feeds from major news outlets."""
        try:
            import feedparser

            feeds = [
                "http://feeds.bbci.co.uk/news/technology/rss.xml",
                "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            ]

            headlines = []
            for feed_url in feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries[:5]:
                        headlines.append(entry.get("title", ""))
                except Exception:
                    continue

            return headlines[:10]

        except ImportError:
            print("[NewsProvider] feedparser not installed for RSS fallback")
            return ["News unavailable - check API key and internet connection"]
