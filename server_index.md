# Server Application (`server.py`) Index

This document provides an overview of the `server.py` application, detailing its functionalities, core components, and API endpoints. The server acts as a backend for a web application, providing integration with Redmine and an AI-powered Retrieval Augmented Generation (RAG) system using Azure OpenAI.

## 1. Introduction

`server.py` is a FastAPI application that serves two primary purposes:

1.  **Redmine Integration:** It connects to Redmine instances to fetch project data, issue details, and allows for AI-driven analysis of project status, as well as updating wiki pages.
2.  **AI-Powered Knowledge Base (RAG):** It allows users to upload various document types (PDF, Word, Excel, Text, Markdown) to build a knowledge base. Users can then query this knowledge base using natural language, and the system retrieves relevant information and generates answers using Azure OpenAI.

## 2. Setup & Configuration

The server relies on environment variables, typically loaded from a `.env` file.

**Key Environment Variables:**

*   `AZURE_OPENAI_API_KEY`: Your Azure OpenAI Service API key.
*   `AZURE_OPENAI_API_VERSION`: The API version for Azure OpenAI (e.g., `2024-02-15-preview`).
*   `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI Service endpoint URL.
*   `AZURE_OPENAI_DEPLOYMENT_NAME`: The deployment name for your chat model (e.g., `gpt-4o-mini-xuxiang`).
*   `AZURE_OPENAI_CHAT_DEPLOYMENT`: (Optional) Specific deployment name for the Langchain chat model, defaults to `AZURE_OPENAI_DEPLOYMENT_NAME`.

**Directory Structure:**

*   `data/`: Stores uploaded documents for the RAG system.
*   `faiss_index/`: Stores the FAISS vector store index generated from documents.

**Dependencies:**

Dependencies are managed in `requirements.txt`. Ensure they are installed using `pip install -r requirements.txt`.

## 3. Core Components

*   **FastAPI:** The web framework for building RESTful APIs.
*   **Pydantic:** Used for data validation and settings management (e.g., `BaseModel` for request/response bodies).
*   **Redminelib:** A Python library for interacting with the Redmine REST API.
*   **Azure OpenAI:** Microsoft's managed OpenAI service, providing LLM capabilities for analysis, query rewriting, and RAG.
*   **Langchain:** An orchestration framework for developing applications powered by language models.
    *   **FAISS:** A library for efficient similarity search and clustering of dense vectors, used as the vector store.
    *   **HuggingFaceEmbeddings:** Provides text embeddings using models like `intfloat/multilingual-e5-base`.
    *   **Document Loaders:** Supports `PyPDFLoader`, `TextLoader`, `UnstructuredWordDocumentLoader`, `UnstructuredExcelLoader`, `UnstructuredMarkdownLoader`.
    *   **RecursiveCharacterTextSplitter:** For breaking large documents into smaller, semantically meaningful chunks.

## 4. RAG System Details

The RAG system allows the server to answer questions based on a private collection of documents.

### 4.1. Document Management

*   **Upload:** Users can upload documents (PDF, DOCX, XLSX, TXT, MD) via an API endpoint. These documents are stored locally in the `data/` directory.
*   **Delete:** Documents can be deleted by filename, which triggers a full re-indexing of the remaining documents.
*   **List:** An endpoint provides a list of all currently stored documents.

### 4.2. Indexing Process

*   When documents are uploaded or deleted, an indexing task is initiated in a **background thread**.
*   Documents are loaded, split into chunks using `RecursiveCharacterTextSplitter`, and then converted into numerical vector embeddings using `HuggingFaceEmbeddings`.
*   These embeddings are stored in a **FAISS vector store** in the `faiss_index/` directory.
*   Progress of indexing tasks is tracked in an in-memory dictionary (`indexing_tasks`) and can be queried via an API endpoint.
*   The `RAGService` class manages the loading and reloading of this vector store and the associated Langchain `RetrievalQA` chain.

### 4.3. Chat with RAG

*   When a user asks a question, the server first uses Azure OpenAI to **rewrite the query** to be more effective for a vector database search.
*   The rewritten query is then used to retrieve relevant document chunks from the FAISS index.
*   These retrieved chunks, along with the original question, are fed into the Azure OpenAI Chat model via Langchain's `RetrievalQA` chain to generate a coherent answer.

## 5. Redmine Integration

The server provides a bridge to Redmine, allowing a frontend application to interact with it.

### 5.1. Authentication

Redmine API calls require `X-Redmine-Url` and `X-Redmine-Api-Key` headers for authentication. A helper `get_redmine_instance` function handles the connection.

### 5.2. Project & Issue Management

*   **List Projects:** Fetches a list of projects from Redmine.
*   **Get Issues:** Retrieves issues associated with a specific Redmine project ID.
*   **Export Data:** Allows exporting project issues into JSON or CSV format.

### 5.3. AI Project Analysis

*   The `/api/analyze` endpoint takes a Redmine `project_id`.
*   It fetches all issues for that project.
*   These issues are then sent to Azure OpenAI with a carefully crafted prompt, requesting a structured analysis focusing on project, schedule, and staffing suggestions.
*   The AI's response is returned in Markdown format.

### 5.4. Wiki Page Management

*   The `/api/projects/{project_identifier}/wiki` endpoint allows updating (creating or modifying) a wiki page within a specified Redmine project.
*   It uses a `PUT` request to Redmine's API and handles various error scenarios (e.g., project not found, authentication failures).

### 5.5. Progress Prediction

*   **Project Progress (`/api/projects/{project_id}/progress-prediction`):**
    *   Calculates and returns weekly planned, actual, and predicted progress for an entire project based on its issues' creation dates, due dates, and status updates.
    *   Includes a summary text indicating whether the project is on track, delayed, or completed.
*   **Issue Progress (`/api/issues/{issue_id}/progress-prediction`):**
    *   Provides daily planned, actual, and predicted progress for a single issue, considering its creation, due, and update dates.
    *   Offers a summary text for individual issue status.

## 6. API Endpoints Summary

| Method | Endpoint                                                  | Description                                                 | Authentication (Redmine Headers) |
| :----- | :-------------------------------------------------------- | :---------------------------------------------------------- | :------------------------------- |
| `GET`  | `/api/rag/documents`                                      | Lists documents in the RAG data directory.                  | None                             |
| `DELETE`| `/api/rag/documents/{filename}`                           | Deletes a document and triggers re-indexing.                | None                             |
| `POST` | `/api/rag/upload`                                         | Uploads documents to the RAG data directory for indexing.   | None                             |
| `GET`  | `/api/rag/progress/{task_id}`                             | Gets the progress of a RAG indexing task.                   | None                             |
| `POST` | `/api/rag/reload`                                         | Reloads the RAG service (reloads FAISS index).              | None                             |
| `POST` | `/api/chat`                                               | Chats with the RAG system; answers questions based on docs. | None                             |
| `GET`  | `/api/projects`                                           | Lists all Redmine projects.                                 | Required                         |
| `GET`  | `/api/projects/{project_id}/issues`                       | Lists issues for a specific Redmine project.                | Required                         |
| `GET`  | `/api/projects/{project_id}/export/{format}`              | Exports project issues in JSON or CSV format.               | Required                         |
| `POST` | `/api/analyze`                                            | Analyzes project issues using Azure OpenAI.                 | Required                         |
| `POST` | `/api/projects/{project_identifier}/wiki`                 | Creates or updates a Redmine wiki page.                     | Required                         |
| `GET`  | `/api/projects/{project_id}/progress-prediction`          | Gets overall project progress prediction data.              | Required                         |
| `GET`  | `/api/issues/{issue_id}/progress-prediction`              | Gets progress prediction data for a single issue.           | Required                         |

## 7. How to Run/Use

1.  **Clone the repository.**
2.  **Install dependencies:** `pip install -r requirements.txt`
3.  **Create a `.env` file** in the project root and populate it with your Azure OpenAI credentials.
4.  **Start the server:** `uvicorn server:app --reload`
    *   The `--reload` flag is useful for development as it restarts the server on code changes.
    *   FastAPI will be accessible typically at `http://127.0.0.1:8000`.
5.  **Access API documentation:** Once running, you can view the interactive API documentation at `http://127.0.0.1:8000/docs` (Swagger UI) or `http://127.00.1:8000/redoc` (ReDoc).

This document should help you understand the structure and capabilities of the `server.py` application.