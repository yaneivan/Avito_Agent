import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./avito_agent.db")

# LLM Configuration
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:8080/v1")
LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "not-needed")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "Qwen3-Vl-4B-Instruct")

# Image storage configuration
IMAGE_STORAGE_PATH = os.getenv("IMAGE_STORAGE_PATH", "./data/images")

# Token limits
MAX_CHAT_HISTORY_TOKENS = int(os.getenv("MAX_CHAT_HISTORY_TOKENS", "4000"))