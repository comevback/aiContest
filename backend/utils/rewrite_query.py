from openai import AzureOpenAI
from backend.core.config import AZURE_OPENAI_DEPLOYMENT_NAME

# This client will need to be initialized and passed or imported from a centralized client module.
# For now, it's a placeholder. The actual client will be initialized in server.py and potentially passed down.
azure_openai_client: AzureOpenAI = None


def initialize_azure_openai_client(client: AzureOpenAI):
    global azure_openai_client
    azure_openai_client = client


def rewrite_query_with_openai(query: str) -> str:
    """
    Rewrites a user's query to be more effective for a vector database search
    using an LLM call.
    """
    if not azure_openai_client:
        print("WARNING: Azure OpenAI client not initialized. Cannot rewrite query.")
        return query

    prompt = f"""If the question is abstract, rewrite it to be more specific for a retrieval-augmented generation system. Only output the rewritten question, without any other text or explanation.

Original question: "{query}"
Rewritten question:"""

    try:
        resp = azure_openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI assistant that rewrites user questions to be more effective for a knowledge base search.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=200,
            stop=None,
        )
        rewritten_query = resp.choices[0].message.content.strip()

        # Clean up the response to get only the query
        rewritten_query = rewritten_query.replace('"', "").strip()
        if "Rewritten question:" in rewritten_query:
            rewritten_query = rewritten_query.split(
                "Rewritten question:")[1].strip()

        print(
            f"Original query: '{query}' | Rewritten query: '{rewritten_query}'")

        # If the model returns an empty string, fall back to the original query
        if not rewritten_query:
            print(
                "WARNING: Query rewrite resulted in an empty string. Falling back to original query."
            )
            return query

        return rewritten_query
    except Exception as e:
        print(f"ERROR: Query rewrite failed: {e}")
        return query  # Fallback to original query on error
