"""Configuration settings for the magi research agent."""

import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Logging setup
LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

# Semantic Scholar
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
SEMANTIC_SCHOLAR_BASE_URL = os.getenv("SEMANTIC_SCHOLAR_BASE_URL")

# OpenRouter
# Available models via OpenRouter:
# - anthropic/claude-3-5-sonnet (balanced)
# - upstage/solar-pro-3:free (free tier)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")
OPENROUTER_DEFAULT_MODEL = os.getenv("OPENROUTER_DEFAULT_MODEL") or "arcee-ai/trinity-mini:free"

# Rate limiting settings
RATE_LIMIT_REQUESTS_PER_SECOND = 10  # With API key
RATE_LIMIT_REQUESTS_PER_SECOND_NO_KEY = 0.05  # Without API key (1 request per 20 seconds)

# Retry settings
MAX_RETRIES = 7
RETRY_BACKOFF_FACTOR = 2.0

# arXiv settings
ARXIV_RATE_LIMIT_SECONDS = float(os.getenv("ARXIV_RATE_LIMIT_SECONDS") or "3.0")
