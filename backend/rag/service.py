import os
from langchain_openai import AzureChatOpenAI as LangchainAzureChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from backend.core.config import (
    INDEX_DIR,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT_NAME,
)


class RAGService:
    def __init__(self, index_dir=INDEX_DIR):
        self.index_dir = index_dir
        self.vectorstore = None
        self.qa_chain = None
        self.embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-base"
        )
        if AZURE_OPENAI_API_KEY:
            self.llm = LangchainAzureChatOpenAI(
                azure_deployment=os.getenv(
                    "AZURE_OPENAI_CHAT_DEPLOYMENT", AZURE_OPENAI_DEPLOYMENT_NAME
                ),
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                openai_api_version=os.getenv(
                    "OPENAI_API_VERSION", AZURE_OPENAI_API_VERSION
                ),
                temperature=0.2,
            )
        else:
            self.llm = None
        self.reload()

    def reload(self) -> bool:
        if not self.llm:
            print(
                "WARNING: RAG service cannot be loaded as Azure OpenAI client is not initialized."
            )
            return False

        print("Attempting to reload RAG service...")
        if not os.path.exists(os.path.join(self.index_dir, "index.faiss")):
            print(
                f"WARNING: RAG index '{self.index_dir}/index.faiss' not found. Cannot load."
            )
            return False

        try:
            self.vectorstore = FAISS.load_local(
                self.index_dir, self.embeddings, allow_dangerous_deserialization=True
            )
            retriever = self.vectorstore.as_retriever(search_kwargs={"k": 8})
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                retriever=retriever,
                return_source_documents=False,
            )
            print("✅ RAG service reloaded successfully.")
            return True
        except Exception as e:
            print(f"ERROR: Failed to reload RAG service: {e}")
            self.qa_chain = None
            return False


# Instantiate the RAG service on server startup
rag_service = RAGService()
