"""
Stock Provider - Fetches stock market data using yfinance.
"""

class StockProvider:
    """
    Provides stock market data using the yfinance library.

    No API key required - uses Yahoo Finance data directly.
    """

    def get_stock_data(self, symbols):
        """
        Fetch current stock data for the given symbols.

        Args:
            symbols: List of stock ticker symbols (e.g., ["AAPL", "GOOGL"])

        Returns:
            dict: {symbol: {"price": str, "change": str, "change_pct": str}}
        """
        try:
            import yfinance as yf
        except ImportError:
            print("[StockProvider] yfinance not installed")
            print("[StockProvider] Install with: pip install yfinance")
            return {s: {"price": "N/A", "change": "N/A", "change_pct": "N/A"} for s in symbols}

        stock_data = {}

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                price = info.get("currentPrice") or info.get("regularMarketPrice", "N/A")
                change = info.get("regularMarketChange", "N/A")
                change_pct = info.get("regularMarketChangePercent", "N/A")

                # Format values
                if isinstance(price, (int, float)):
                    price = f"${price:.2f}"
                if isinstance(change, (int, float)):
                    change = f"{change:+.2f}"
                if isinstance(change_pct, (int, float)):
                    change_pct = f"{change_pct:+.2f}%"

                stock_data[symbol] = {
                    "price": str(price),
                    "change": str(change),
                    "change_pct": str(change_pct),
                }

            except Exception as e:
                print(f"[StockProvider] Error fetching {symbol}: {e}")
                stock_data[symbol] = {
                    "price": "Error",
                    "change": "Error",
                    "change_pct": "Error",
                }

        return stock_data

    def get_market_summary(self):
        """
        Get a general market summary text.

        Returns:
            str: Spoken summary of market conditions
        """
        try:
            import yfinance as yf

            # Check major indices
            indices = {
                "^GSPC": "S&P 500",
                "^DJI": "Dow Jones",
                "^IXIC": "NASDAQ",
            }

            summary_parts = []
            for symbol, name in indices.items():
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    change_pct = info.get("regularMarketChangePercent", 0)
                    if isinstance(change_pct, (int, float)):
                        direction = "up" if change_pct > 0 else "down"
                        summary_parts.append(
                            f"{name} is {direction} {abs(change_pct):.2f}%"
                        )
                except Exception:
                    pass

            if summary_parts:
                return "The market summary: " + ", ".join(summary_parts) + "."
            else:
                return "Market data is currently unavailable."

        except ImportError:
            return "Market data unavailable - yfinance not installed."
