import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Global State & Config ---
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini-xuxiang"
)
DATA_DIR = "data"
INDEX_DIR = "faiss_index"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)
