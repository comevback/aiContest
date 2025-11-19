from fastapi import FastAPI, HTTPException, Response, Header, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import os
import shutil
import uuid
import threading
from dotenv import load_dotenv
from redminelib import Redmine
from redminelib.exceptions import AuthError, ResourceNotFoundError
from openai import AzureOpenAI, APIConnectionError, APIStatusError
import re
import csv
import io
from datetime import datetime, timedelta, date
import json
import requests
from urllib.parse import quote
from typing import List, Optional, Dict

# --- RAG Imports ---
from langchain_openai import AzureChatOpenAI as LangchainAzureChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm

# Load environment variables from .env file
load_dotenv()

# --- App and Middleware Setup ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Redmine-Url", "X-Redmine-Api-Key"],
)

# --- Global State & Config ---
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini-xuxiang")
DATA_DIR = "data"
INDEX_DIR = "faiss_index"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)

# In-memory storage for indexing task progress
indexing_tasks: Dict[str, Dict] = {}

# --- Azure OpenAI Client Initialization ---
azure_openai_client = None
if AZURE_OPENAI_API_KEY:
    try:
        azure_openai_client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
        )
        print("Successfully initialized Azure OpenAI client.")
    except Exception as e:
        print(f"WARNING: Failed to initialize Azure OpenAI client: {e}")
else:
    print("WARNING: Azure OpenAI API key not provided. AI analysis will be disabled.")

# --- RAG Indexing Logic (Refactored from build_index.py) ---


class TqdmProgressWriter:
    """A file-like object to capture tqdm progress."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.buffer = ""

    def write(self, s: str):
        self.buffer += s
        match = re.search(r"(\d+)%", self.buffer)
        if match:
            progress = int(match.group(1))
            if self.task_id in indexing_tasks:
                indexing_tasks[self.task_id]['progress'] = progress
            self.buffer = ""  # Reset buffer

    def flush(self):
        pass


def run_indexing(task_id: str, file_paths: List[str]):
    """
    Runs the document indexing process for multiple file types in a background thread.
    Updates the global `indexing_tasks` dictionary with progress.
    """
    task = indexing_tasks[task_id]
    task['status'] = 'processing'
    task['message'] = 'Initializing...'

    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-base")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=100)

        task['message'] = 'Loading and splitting documents...'
        all_chunks = []
        processed_files = []
        ignored_files = []

        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_name)[1].lower()
            loader = None

            try:
                if file_ext == ".pdf":
                    loader = PyPDFLoader(file_path)
                elif file_ext == ".docx":
                    loader = UnstructuredWordDocumentLoader(file_path)
                elif file_ext in [".xlsx", ".xls"]:
                    loader = UnstructuredExcelLoader(
                        file_path, mode="elements")
                elif file_ext == ".txt":
                    loader = TextLoader(file_path, encoding="utf-8")
                elif file_ext == ".md":
                    loader = UnstructuredMarkdownLoader(file_path)
                else:
                    ignored_files.append(file_name)
                    print(f"Ignoring unsupported file type: {file_name}")
                    continue

                print(f"Processing file: {file_name}")
                docs = loader.load()
                chunks = splitter.split_documents(docs)
                for chunk in chunks:
                    chunk.metadata['source'] = file_name
                all_chunks.extend(chunks)
                processed_files.append(file_name)

            except Exception as e:
                ignored_files.append(file_name)
                print(f"ERROR: Failed to process file {file_name}: {e}")

        if not all_chunks:
            task['status'] = 'failed'
            task['message'] = f'No content could be extracted. Processed {len(processed_files)}, ignored {len(ignored_files)} files.'
            return

        task['total'] = len(all_chunks)
        task['progress'] = 0
        task['message'] = f'Embedding {len(all_chunks)} document chunks...'

        vectorstore = None
        if os.path.exists(os.path.join(INDEX_DIR, "index.faiss")):
            vectorstore = FAISS.load_local(
                INDEX_DIR, embeddings, allow_dangerous_deserialization=True)

        batch_size = 32
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i+batch_size]
            if vectorstore is None and i == 0:
                vectorstore = FAISS.from_documents(batch, embeddings)
            elif vectorstore is not None:
                vectorstore.add_documents(batch)

            # Update progress
            progress_percent = min(
                100, int(((i + len(batch)) / len(all_chunks)) * 100))
            task['progress'] = progress_percent
            task['message'] = f'Embedding documents... ({i+len(batch)}/{len(all_chunks)})'

        if vectorstore:
            vectorstore.save_local(INDEX_DIR)

        task['status'] = 'completed'
        task['progress'] = 100
        task['message'] = f"Success! Indexed {len(all_chunks)} chunks from {len(processed_files)} files. Ignored {len(ignored_files)} files."

    except Exception as e:
        task['status'] = 'failed'
        task['message'] = f"An unexpected error occurred during indexing: {str(e)}"
        print(f"[Indexing Task {task_id}] Failed: {e}")

# --- RAG Service and Models ---


class RAGService:
    def __init__(self, index_dir=INDEX_DIR):
        self.index_dir = index_dir
        self.vectorstore = None
        self.qa_chain = None
        self.embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-base")
        if AZURE_OPENAI_API_KEY:
            self.llm = LangchainAzureChatOpenAI(
                azure_deployment=os.getenv(
                    "AZURE_OPENAI_CHAT_DEPLOYMENT", AZURE_OPENAI_DEPLOYMENT_NAME),
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                openai_api_version=os.getenv(
                    "OPENAI_API_VERSION", AZURE_OPENAI_API_VERSION),
                temperature=0.2,
            )
        else:
            self.llm = None
        self.reload()

    def reload(self) -> bool:
        if not self.llm:
            print(
                "WARNING: RAG service cannot be loaded as Azure OpenAI client is not initialized.")
            return False

        print("Attempting to reload RAG service...")
        if not os.path.exists(os.path.join(self.index_dir, "index.faiss")):
            print(
                f"WARNING: RAG index '{self.index_dir}/index.faiss' not found. Cannot load.")
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

# Pydantic Models for APIs


class ChatRequest(BaseModel):
    question: str


class SourceDocument(BaseModel):
    source: Optional[str] = None
    page_content: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]


class ProjectAnalysisRequest(BaseModel):
    project_id: str


class WikiPageUpdateRequest(BaseModel):
    title: str
    content: str
    comment: str = ""

# --- Helper Functions ---


def strip_markdown_fence(text: str) -> str:
    if not text:
        return text
    text = text.strip()
    pattern = r"^```(?:markdown|md)?\s*([\s\S]*?)\s*```$"
    match = re.match(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else re.sub(r"^```(?:markdown|md)?|```$", "", text, flags=re.MULTILINE).strip()


def get_redmine_instance(redmine_url: str, redmine_api_key: str):
    if not redmine_url or not redmine_api_key:
        raise HTTPException(
            status_code=400, detail="Redmine URL and API Key are required.")
    try:
        redmine = Redmine(redmine_url, key=redmine_api_key)
        redmine.auth()
        return redmine
    except AuthError:
        raise HTTPException(
            status_code=401, detail="Failed to authenticate with Redmine.")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to Redmine: {e}")

# --- API Endpoints ---

# RAG Endpoints


@app.get("/api/rag/documents")
async def get_rag_documents():
    """Returns a list of documents in the RAG data directory."""
    if not os.path.isdir(DATA_DIR):
        return {"documents": []}
    try:
        # Filter out directories, return only files
        documents = [f for f in os.listdir(
            DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list documents: {e}")


@app.delete("/api/rag/documents/{filename}")
async def delete_rag_document(filename: str):
    """Deletes a document and triggers a full re-indexing of the knowledge base."""
    try:
        # Sanitize filename to prevent directory traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename.")

        file_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found.")

        # 1. Delete the actual document file
        os.remove(file_path)

        # 2. Delete the FAISS index to force a rebuild
        index_file = os.path.join(INDEX_DIR, "index.faiss")
        pkl_file = os.path.join(INDEX_DIR, "index.pkl")
        if os.path.exists(index_file):
            os.remove(index_file)
        if os.path.exists(pkl_file):
            os.remove(pkl_file)

        # 3. Get remaining files and trigger re-indexing
        remaining_files = [os.path.join(DATA_DIR, f) for f in os.listdir(
            DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]

        task_id = str(uuid.uuid4())
        message = "File deleted. Starting full re-index..."
        if not remaining_files:
            message = "File deleted. Knowledge base is now empty."
            # No need to run indexing if no files are left
            indexing_tasks[task_id] = {
                "status": "completed", "progress": 100, "total": 100, "message": message}
            # Also reload the service to clear the in-memory index
            rag_service.reload()
        else:
            indexing_tasks[task_id] = {"status": "pending", "progress": 0,
                                       "total": 100, "message": "Task queued for re-indexing"}
            thread = threading.Thread(
                target=run_indexing, args=(task_id, remaining_files))
            thread.start()

        return {"task_id": task_id, "message": message}

    except HTTPException as e:
        raise e  # Re-raise HTTPException
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete document: {e}")


@app.post("/api/rag/upload")
async def upload_rag_documents(files: List[UploadFile] = File(...)):
    task_id = str(uuid.uuid4())
    file_paths = []

    for file in files:
        file_location = os.path.join(DATA_DIR, file.filename)
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        file_paths.append(file_location)

    indexing_tasks[task_id] = {
        "status": "pending", "progress": 0, "total": 100, "message": "Task queued"}

    thread = threading.Thread(target=run_indexing, args=(task_id, file_paths))
    thread.start()

    return {"task_id": task_id, "message": "File upload successful, indexing started."}


@app.get("/api/rag/progress/{task_id}")
async def get_indexing_progress(task_id: str):
    task = indexing_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@app.post("/api/rag/reload")
async def reload_rag_endpoint():
    if rag_service.reload():
        return {"message": "RAG service reloaded successfully."}
    raise HTTPException(
        status_code=500, detail="Failed to reload RAG service. Check server logs.")


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_rag(request: ChatRequest):
    if not rag_service or not rag_service.qa_chain:
        raise HTTPException(
            status_code=503, detail="RAG service is not available.")
    try:
        result = rag_service.qa_chain.invoke(request.question)
        return ChatResponse(answer=result.get("result", "No answer found."), sources=[])
    except Exception as e:
        print(f"ERROR: RAG chat processing failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"An error occurred during chat processing: {e}")

# Existing Redmine Endpoints


@app.get("/api/projects")
async def get_projects(x_redmine_url: str = Header(..., alias="X-Redmine-Url"), x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key")):
    redmine = get_redmine_instance(x_redmine_url, x_redmine_api_key)
    try:
        projects = redmine.project.all(limit=100)
        return {"projects": [{"id": p.id, "name": p.name, "identifier": p.identifier} for p in projects]}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch projects from Redmine: {e}")


@app.get("/api/projects/{project_id}/issues")
async def get_issues(
    project_id: int,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key")
):
    """Returns issues for a given project ID from Redmine."""
    redmine = get_redmine_instance(x_redmine_url, x_redmine_api_key)
    try:
        issues = redmine.issue.filter(
            project_id=project_id, limit=100)
        issue_list = []
        for issue in issues:
            issue_data = {
                "id": issue.id,
                "subject": issue.subject,
                "status": {"name": issue.status.name} if hasattr(issue.status, 'name') else None,
                "priority": {"name": issue.priority.name} if hasattr(issue.priority, 'name') else None,
                "assigned_to": {"name": issue.assigned_to.name} if hasattr(issue, 'assigned_to') else None,
                "created_on": str(issue.created_on) if hasattr(issue, 'created_on') else None,
                "updated_on": str(issue.updated_on) if hasattr(issue, 'updated_on') else None,
                "due_date": str(issue.due_date) if hasattr(issue, 'due_date') else None,
            }
            issue_list.append(issue_data)
        return {"issues": issue_list}
    except ResourceNotFoundError:
        print(f"ERROR: Project {project_id} not found in Redmine.")
        raise HTTPException(
            status_code=404, detail="Project not found in Redmine")
    except Exception as e:
        print(
            f"ERROR: Failed to fetch issues for project {project_id} from Redmine: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch issues from Redmine: {e}")


@app.get("/api/projects/{project_id}/export/{format}")
async def export_data(
    project_id: int,
    format: str,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key")
):
    """Exports project data in various formats."""
    redmine = get_redmine_instance(x_redmine_url, x_redmine_api_key)
    try:
        issues = redmine.issue.filter(project_id=project_id, limit=100)
        if not issues:
            raise HTTPException(
                status_code=404, detail=f"No issues found for project {project_id}")

        issue_data = []
        for issue in issues:
            issue_data.append({
                "id": issue.id,
                "subject": issue.subject,
                "status": issue.status.name if hasattr(issue.status, 'name') else None,
                "priority": issue.priority.name if hasattr(issue.priority, 'name') else None,
                "assigned_to": issue.assigned_to.name if hasattr(issue, 'assigned_to') else None,
                "created_on": str(issue.created_on) if hasattr(issue, 'created_on') else None,
                "updated_on": str(issue.updated_on) if hasattr(issue, 'updated_on') else None,
                "due_date": str(issue.due_date) if hasattr(issue, 'due_date') else None,
            })

        if format == "json":
            return Response(content=json.dumps(issue_data, indent=2), media_type="application/json", headers={"Content-Disposition": f"attachment; filename=project_{project_id}_issues.json"})
        elif format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            # Write header
            if issue_data:
                writer.writerow(issue_data[0].keys())
            # Write data
            for row in issue_data:
                writer.writerow(row.values())
            return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=project_{project_id}_issues.csv"})
        elif format == "excel":
            return {"message": "Excel export not implemented. Please use CSV or JSON."}
        elif format == "pdf":
            return {"message": "PDF export not implemented. Please use CSV or JSON."}
        else:
            raise HTTPException(
                status_code=400, detail="Invalid export format. Supported formats: json, csv, excel, pdf")
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404, detail="Project not found in Redmine")
    except Exception as e:
        print(f"ERROR: Failed to export data for project {project_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to export data: {e}")


@app.post("/api/analyze")
async def analyze_project(
    request_body: ProjectAnalysisRequest,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key")
):
    """Analyzes project issues using Azure OpenAI."""
    redmine = get_redmine_instance(x_redmine_url, x_redmine_api_key)
    project_id = request_body.project_id

    if not azure_openai_client:
        print("ERROR: Azure OpenAI client not initialized. AI analysis cannot proceed.")
        raise HTTPException(
            status_code=500, detail="Azure OpenAI client not initialized. Check API key and endpoint.")

    try:
        print(
            f"Attempting to fetch issues for project {project_id} from Redmine...")
        project_issues = redmine.issue.filter(project_id=project_id, limit=100)
        if not project_issues:
            print(
                f"INFO: No issues found for project {project_id}. No analysis performed.")
            return {"analysis": f"No issues found for project {project_id}. No analysis performed."}

        issues_text = ""
        for issue in project_issues:
            # Safely get description and clean it up for the prompt
            description = getattr(issue, 'description', '説明なし').replace(
                '\n', ' ').replace('\r', '')
            issues_text += f"- ID: {issue.id}, Subject: {issue.subject}, Status: {issue.status.name}, Priority: {issue.priority.name}, Description: {description}\n"

        print(
            f"Sending {len(project_issues)} issues to Azure OpenAI for analysis...")
        analysis_result = analyze_redmine_issues_with_openai(issues_text)
        print("AI analysis completed successfully.")
        return {"analysis": analysis_result}
    except ResourceNotFoundError:
        print(
            f"ERROR: Project {project_id} not found in Redmine during AI analysis.")
        raise HTTPException(
            status_code=404, detail="Project not found in Redmine")
    except (APIConnectionError, APIStatusError) as e:
        print(f"ERROR: Azure OpenAI API call failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Azure OpenAI API call failed: {e}")
    except Exception as e:
        print(f"ERROR: AI analysis failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")


def analyze_redmine_issues_with_openai(issues_str: str) -> str:
    prompt = (
        "あなたは経験豊富なプロジェクトマネジメントコンサルタントです。"
        "以下の Redmine チケット一覧に基づき、構造的で実行可能な分析提案を日本語で出力してください。\n\n"
        "次の形式に厳密に従ってください：\n"
        "## プロジェクトに関する提案：...\n"
        "## スケジュール管理に関する提案：...\n"
        "## 人員配置に関する提案：...\n\n"
        "【出力に関する指示】\n"
        "- 「プロジェクトに関する提案」では、全体の進捗、リスク、優先度の観点から改善点を述べてください。\n"
        "- 「スケジュール管理に関する提案」では、締切、遅延、リソース配分の妥当性を分析してください。\n"
        "- 「人員配置に関する提案」では、担当者の負荷や役割分担を考慮した改善案を示してください。\n"
        "\n以下は Redmine チケットの一覧です：\n\n"
        + issues_str
    )

    example = (
        '''
        ### 例：AI プロジェクトの分析レポート

        ## プロジェクトに関する提案：
        現在、複数のチケットが「新規」状態であり、優先度の高いタスク（例：「緊急バグ修正1」）が未対応です。
        これらの重要タスクを最優先で対応し、定期的に進捗をレビューする体制を整えることを推奨します。
        プロジェクト全体の進捗とリスクを定量的に把握し、優先順位を動的に見直すことで効率を高めることができます。

        ## スケジュール管理に関する提案：
        「緊急バグ修正1」の期限は2025年10月21日と迫っているため、即時対応が必要です。
        一方、「新機能開発1」は10月24日締めで、優先度も高いため、バグ修正後すぐに着手できるようリソースを確保するべきです。
        期限が設定されていない「サポート」チケットには、明確なスケジュールを設けることで遅延を防げます。

        ## 人員配置に関する提案：
        すべてのチケットが同一担当者（Redmine Admin）に割り当てられているため、負荷の偏りが見られます。
        メンバーのスキルとタスクの難易度を考慮し、適切に分担を行うことでチーム全体の生産性を向上できます。
        特に優先度の高いタスクは複数の担当者で並行処理できるよう体制を見直してください。
        '''
    )

    if not azure_openai_client:
        raise ValueError("Azure OpenAI クライアントが初期化されていません。")

    try:
        resp = azure_openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはプロジェクトマネジメントの専門家です。"
                        "必ず Markdown 形式で出力し、必要に応じて ``` コードブロックを使用してください。"
                        "出力形式は次の例に従ってください：" + example
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        open_ai_response = resp.choices[0].message.content
        openai_clean = strip_markdown_fence(open_ai_response)
        print("Raw OpenAI Response:\n" + open_ai_response)
        return openai_clean
    except Exception as e:
        print(f"Azure OpenAI API 呼び出しエラー: {e}")
        raise e


def upsert_wiki_page(base_url: str, project_identifier: str, title: str, text: str, api_key: str, comment: str = ""):
    """
    Creates or updates a wiki page in Redmine.
    """
    url = f"{base_url}/projects/{project_identifier}/wiki/{quote(title)}.json"
    headers = {
        "X-Redmine-API-Key": api_key,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    payload = {"wiki_page": {"text": text, "comments": comment}}

    try:
        # Use PUT to create or update the wiki page
        r = requests.put(url, data=json.dumps(
            payload, ensure_ascii=False).encode("utf-8"), headers=headers)
        r.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # After successful update, get the page details to confirm
        g = requests.get(url, headers=headers)
        g.raise_for_status()

        if g.headers.get("Content-Type", "").startswith("application/json"):
            page = g.json().get("wiki_page", {})
            return {
                "ok": True,
                "title": page.get("title", title),
                "version": page.get("version"),
                "browser_url": f"{base_url}/projects/{project_identifier}/wiki/{quote(title)}"
            }
        else:
            # This case should ideally not be reached if the PUT was successful
            return {"ok": False, "status": g.status_code, "body": g.text}

    except requests.exceptions.RequestException as e:
        print(
            f"ERROR: Failed to upsert wiki page '{title}' for project '{project_identifier}': {e}")
        # Try to provide a more specific error message based on the response
        if e.response is not None:
            status_code = e.response.status_code
            if status_code == 404:
                raise HTTPException(
                    status_code=404, detail=f"Project '{project_identifier}' or wiki page not found. Ensure the project identifier is correct.")
            elif status_code == 401:
                raise HTTPException(
                    status_code=401, detail="Redmine authentication failed. Check your API key.")
            elif status_code == 403:
                raise HTTPException(
                    status_code=403, detail="You do not have permission to edit the wiki on this project.")
            else:
                raise HTTPException(
                    status_code=status_code, detail=f"Redmine API error: {e.response.text}")
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to connect to Redmine: {e}")


@app.post("/api/projects/{project_identifier}/wiki")
async def update_wiki(
    project_identifier: str,
    request_body: WikiPageUpdateRequest,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key")
):
    """Updates a Redmine wiki page with the given content."""
    try:
        result = upsert_wiki_page(
            base_url=x_redmine_url,
            project_identifier=project_identifier,
            title=request_body.title,
            text=request_body.content,
            api_key=x_redmine_api_key,
            comment=request_body.comment
        )
        if result.get("ok"):
            return {"message": "Wiki page updated successfully.", "details": result}
        else:
            # This part might be redundant if upsert_wiki_page raises HTTPException
            raise HTTPException(status_code=result.get(
                "status", 500), detail=result.get("body", "Failed to update wiki page."))
    except HTTPException as e:
        # Re-raise HTTPException to let FastAPI handle it
        raise e
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while updating wiki: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/projects/{project_id}/progress-prediction")
async def get_project_progress_prediction(
    project_id: int,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key")
):
    """Returns overall project progress prediction data."""
    redmine = get_redmine_instance(x_redmine_url, x_redmine_api_key)
    try:
        issues = redmine.issue.filter(project_id=project_id, limit=100)
        if not issues:
            raise HTTPException(
                status_code=404, detail=f"No issues found for project {project_id}")

        # Sort issues by creation date to establish a timeline
        issues_sorted_by_created = sorted(issues, key=lambda i: i.created_on)

        if not issues_sorted_by_created:
            return {"progress_data": [], "summary": "No issues to predict progress."}

        # Determine project start and end dates
        project_start_date = issues_sorted_by_created[0].created_on.date() if isinstance(
            issues_sorted_by_created[0].created_on, datetime) else issues_sorted_by_created[0].created_on

        all_due_dates = []
        for issue in issues:
            if hasattr(issue, 'due_date') and issue.due_date:
                if isinstance(issue.due_date, datetime):
                    all_due_dates.append(issue.due_date.date())
                elif isinstance(issue.due_date, date):
                    all_due_dates.append(issue.due_date)

        if not all_due_dates:
            project_end_date = project_start_date + \
                timedelta(weeks=6)  # Fallback if no due dates
        else:
            project_end_date = max(all_due_dates)

        today = datetime.now().date()

        # Adjust project_end_date if it's in the past
        if project_end_date < today:
            # Extend prediction 2 weeks into future
            project_end_date = today + timedelta(weeks=2)

        total_duration_days = (project_end_date - project_start_date).days
        if total_duration_days <= 0:
            total_duration_days = 1  # Avoid division by zero

        progress_data = []
        total_issues_count = len(issues)

        # Calculate weekly progress
        current_week_start = project_start_date
        week_num = 0
        # Go two weeks beyond end for prediction
        while current_week_start <= project_end_date + timedelta(weeks=2):
            week_num += 1
            week_end = current_week_start + timedelta(days=6)
            week_label = f"Week {week_num}"

            # Planned: Straight line from 0% at project_start_date to 100% at project_end_date
            days_passed_planned = (week_end - project_start_date).days
            planned_progress = min(
                100, max(0, (days_passed_planned / total_duration_days) * 100))

            # Actual: Issues completed by this week
            completed_by_week = [issue for issue in issues if
                                 hasattr(issue.status, 'name') and
                                 issue.status.name.lower() in ['closed', 'resolved', '完了', '解決'] and
                                 (issue.updated_on.date() if isinstance(issue.updated_on, datetime) else issue.updated_on) <= week_end]
            actual_progress = (len(
                completed_by_week) / total_issues_count) * 100 if total_issues_count > 0 else 0
            actual_progress = round(
                actual_progress) if current_week_start <= today else None

            # Predicted: Simple extrapolation of current velocity
            predicted_progress_val = None
            if actual_progress is not None:  # If we have actual data for this week
                predicted_progress_val = actual_progress
            elif progress_data:  # Extrapolate from last known actual progress
                last_known_actual = 0
                last_known_week_index = 0
                for i, pd in enumerate(progress_data):
                    if pd["actual"] is not None:
                        last_known_actual = pd["actual"]
                        last_known_week_index = i

                # Calculate average weekly velocity from start to last known actual
                if last_known_week_index > 0:
                    avg_weekly_velocity = last_known_actual / last_known_week_index
                else:
                    avg_weekly_velocity = 0

                # Project forward
                projected_progress = last_known_actual + avg_weekly_velocity * \
                    (week_num - (last_known_week_index + 1))
                predicted_progress_val = min(100, max(0, projected_progress))
            else:
                predicted_progress_val = 0  # Default if no actual data yet

            progress_data.append({
                "week": week_label,
                "planned": round(planned_progress),
                "actual": actual_progress,
                "predicted": round(predicted_progress_val) if predicted_progress_val is not None else None,
            })
            current_week_start += timedelta(days=7)

        # Generate summary text
        current_completion_rate = 0
        if total_issues_count > 0:
            completed_issues_today = len([issue for issue in issues if hasattr(issue.status, 'name') and issue.status.name.lower() in [
                                         'closed', 'resolved', '完了', '解決'] and (issue.updated_on.date() if isinstance(issue.updated_on, datetime) else issue.updated_on) <= today])
            current_completion_rate = (
                completed_issues_today / total_issues_count) * 100

        current_planned_progress = 0
        days_passed_since_start = (today - project_start_date).days
        if days_passed_since_start > 0:
            current_planned_progress = min(
                100, max(0, (days_passed_since_start / total_duration_days) * 100))

        if current_completion_rate >= 100:
            summary_text = "プロジェクトは完了しました。"
        elif current_completion_rate >= current_planned_progress - 5:  # 計画との差が5％以内
            summary_text = "プロジェクトは計画通りに進行しており、予定通りに完了する見込みです。"
        elif current_completion_rate < current_planned_progress - 5:
            summary_text = "プロジェクトの進捗が計画より遅れており、納期遅延のリスクがあります。早急な対応を推奨します。"
        else:
            summary_text = "プロジェクトは進行中です。進捗状況を引き続き注視してください。"

        return {"progress_data": progress_data, "summary": summary_text}
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404, detail="Project not found in Redmine")
    except Exception as e:
        print(
            f"ERROR: Failed to get progress prediction for project {project_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get progress prediction: {e}")


@app.get("/api/issues/{issue_id}/progress-prediction")
async def get_issue_progress_prediction(
    issue_id: int,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key")
):
    """Returns progress prediction data for a single issue."""
    redmine = get_redmine_instance(x_redmine_url, x_redmine_api_key)
    try:
        issue = redmine.issue.get(issue_id)
        if not issue:
            raise HTTPException(
                status_code=404, detail=f"Issue {issue_id} not found in Redmine")

        issue_start_date = issue.created_on.date() if isinstance(
            issue.created_on, datetime) else issue.created_on
        issue_due_date = None
        if hasattr(issue, 'due_date') and issue.due_date:
            issue_due_date = issue.due_date.date() if isinstance(
                issue.due_date, datetime) else issue.due_date

        if not issue_due_date:
            print(
                f"ERROR: Issue {issue_id} does not have a due date for prediction.")
            raise HTTPException(
                status_code=400, detail=f"Issue {issue_id} does not have a due date for prediction.")

        today = datetime.now().date()

        total_duration_days = (issue_due_date - issue_start_date).days
        if total_duration_days <= 0:
            total_duration_days = 1  # Avoid division by zero

        progress_data = []

        # Calculate daily progress for a finer granularity for single issue
        current_day = issue_start_date
        day_num = 0
        # Go one week beyond due date
        while current_day <= issue_due_date + timedelta(days=7):
            day_num += 1
            day_label = current_day.strftime("%Y-%m-%d")

            # Planned: Straight line from 0% at issue_start_date to 100% at issue_due_date
            days_passed_planned = (current_day - issue_start_date).days
            planned_progress = min(
                100, max(0, (days_passed_planned / total_duration_days) * 100))

            # Actual: 0% until updated_on (if status is not new), 100% if closed/resolved by current_day
            actual_progress = 0
            is_completed = hasattr(issue.status, 'name') and issue.status.name.lower() in [
                'closed', 'resolved', '完了', '解決']
            issue_updated_date = issue.updated_on.date() if hasattr(issue, 'updated_on') and isinstance(
                issue.updated_on, datetime) else issue.created_on.date()

            if is_completed and issue_updated_date <= current_day:
                actual_progress = 100
            elif issue_updated_date <= current_day and issue.status.name.lower() not in ['new', 'open', '新建', '开放']:
                # Simple linear interpolation for in-progress issues
                progress_since_start = (current_day - issue_start_date).days
                # Assume 80% of planned velocity
                actual_progress = min(
                    100, max(0, (progress_since_start / total_duration_days) * 100 * 0.8))

            # Predicted: Assume 100% by due date if not yet completed, otherwise follow actual
            predicted_progress = actual_progress
            if current_day > today and not is_completed:
                # Simple linear projection to 100% by due date
                days_remaining = (issue_due_date - current_day).days
                if days_remaining > 0:
                    predicted_progress = min(
                        100, max(actual_progress, 100 - (days_remaining / total_duration_days) * 100))
                else:
                    predicted_progress = 100  # If past due, assume 100% for prediction

            progress_data.append({
                "week": day_label,  # Using day_label for finer granularity
                "planned": round(planned_progress),
                "actual": round(actual_progress) if current_day <= today else None,
                "predicted": round(predicted_progress) if predicted_progress is not None else None,
            })
            current_day += timedelta(days=1)

        # Generate summary text for individual issue
        is_completed = hasattr(issue.status, 'name') and issue.status.name.lower() in [
            'closed', 'resolved', '完了', '解決']
        issue_updated_date = issue.updated_on.date() if hasattr(issue, 'updated_on') and isinstance(
            issue.updated_on, datetime) else issue.created_on.date()

        if is_completed:
            summary_text = f"チケット {issue.id} は {issue_updated_date} に完了しました。"
        elif today > issue_due_date:
            summary_text = f"チケット {issue.id} は期限を過ぎています。元の締切日は {issue_due_date} です。"
        elif predicted_progress >= 95:
            summary_text = f"チケット {issue.id} は予定通り完了する見込みです。"
        else:
            summary_text = f"チケット {issue.id} は進行中です。予定完了日は {issue_due_date} です。"

        return {"progress_data": progress_data, "summary": summary_text}
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404, detail="Issue not found in Redmine")
    except HTTPException as e:  # Catch HTTPException directly
        print(
            f"ERROR: Progress prediction for issue {issue_id} failed: {e.detail}")
        raise e  # Re-raise the HTTPException
    except Exception as e:
        print(
            f"ERROR: Failed to get progress prediction for issue {issue_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get progress prediction for issue: {e}")
