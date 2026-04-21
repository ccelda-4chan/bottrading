import requests
from loguru import logger
import time

class NewsClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"

    def get_crypto_news(self, query="crypto OR bitcoin OR ethereum", page_size=5):
        """
        Fetch latest crypto news.
        """
        url = f"{self.base_url}/everything"
        params = {
            "q": query,
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": self.api_key,
            "language": "en"
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "ok":
                return data.get("articles", [])
            else:
                logger.error(f"NewsAPI Error: {data.get('message')}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch news: {e}")
            return []

    def get_sentiment(self, text):
        """
        Very basic keyword-based sentiment analysis.
        In a real app, one would use NLP like TextBlob, VADER or an LLM.
        """
        bullish_words = ["surge", "bullish", "moon", "buy", "growth", "high", "gain", "breakthrough", "adoption", "etf", "halving"]
        bearish_words = ["crash", "bearish", "sell", "drop", "low", "loss", "hack", "scam", "regulation", "ban", "dump"]
        
        text = text.lower()
        score = 0
        for word in bullish_words:
            if word in text:
                score += 1
        for word in bearish_words:
            if word in text:
                score -= 1
        
        return score
