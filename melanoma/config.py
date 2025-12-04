"""Configuration for the extractor system.

This module handles environment variables and configuration settings.
"""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI API Key
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

# Database Configuration
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///extraction.db")

# Logging Configuration
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# GPT-4o Mini Configuration
DEFAULT_MODEL: str = "gpt-4o-mini"
DEFAULT_TEMPERATURE: float = 0.1
DEFAULT_MAX_TOKENS: int = 1000

# Extraction Configuration
DEFAULT_CONTEXT_CHUNKS: int = 5
DEFAULT_SIMILARITY_THRESHOLD: float = 0.1
