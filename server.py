from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AzureOpenAI, APIConnectionError, APIStatusError

from backend.core.config import AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_ENDPOINT
from backend.core.logger import logger
from backend.rag import routes as rag_routes
from backend.redmine import routes as redmine_routes
from backend.redmine.analysis import initialize_azure_openai_client as init_analysis_client
from backend.utils.rewrite_query import initialize_azure_openai_client as init_rewrite_client

# --- App and Middleware Setup ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Redmine-Url", "X-Redmine-Api-Key"],
)

# --- Azure OpenAI Client Initialization ---
azure_openai_client = None
if AZURE_OPENAI_API_KEY:
    try:
        azure_openai_client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
        )
        logger.info("Successfully initialized Azure OpenAI client.")
        init_analysis_client(azure_openai_client)
        init_rewrite_client(azure_openai_client)
    except Exception as e:
        logger.warning(f"Failed to initialize Azure OpenAI client: {e}")
else:
    logger.warning(
        "Azure OpenAI API key not provided. AI analysis will be disabled.")

# --- Include Routers ---
app.include_router(rag_routes.router, prefix="/api")
app.include_router(redmine_routes.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Welcome to the SPA!"}
