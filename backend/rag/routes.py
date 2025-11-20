from fastapi import APIRouter, HTTPException, File, UploadFile
import os
import shutil
import uuid
import threading
from typing import List, Dict

from backend.rag.models import ChatRequest, ChatResponse
from backend.rag.indexing import indexing_tasks, run_indexing
from backend.rag.service import rag_service
from backend.core.config import DATA_DIR
from backend.utils.rewrite_query import rewrite_query_with_openai

router = APIRouter()


@router.get("/rag/documents")
async def get_rag_documents():
    """Returns a list of documents in the RAG data directory."""
    if not os.path.isdir(DATA_DIR):
        return {"documents": []}
    try:
        # Filter out directories, return only files
        documents = [
            f for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))
        ]
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list documents: {e}")


@router.delete("/rag/documents/{filename}")
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
        remaining_files = [
            os.path.join(DATA_DIR, f)
            for f in os.listdir(DATA_DIR)
            if os.path.isfile(os.path.join(DATA_DIR, f))
        ]

        task_id = str(uuid.uuid4())
        message = "File deleted. Starting full re-index..."
        if not remaining_files:
            message = "File deleted. Knowledge base is now empty."
            # No need to run indexing if no files are left
            indexing_tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "total": 100,
                "message": message,
            }
            # Also reload the service to clear the in-memory index
            rag_service.reload()
        else:
            indexing_tasks[task_id] = {
                "status": "pending",
                "progress": 0,
                "total": 100,
                "message": "Task queued for re-indexing",
            }
            thread = threading.Thread(
                target=run_indexing, args=(task_id, remaining_files)
            )
            thread.start()

        return {"task_id": task_id, "message": message}

    except HTTPException as e:
        raise e  # Re-raise HTTPException
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete document: {e}")


@router.post("/rag/upload")
async def upload_rag_documents(files: List[UploadFile] = File(...)):
    task_id = str(uuid.uuid4())
    file_paths = []

    for file in files:
        file_location = os.path.join(DATA_DIR, file.filename)
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        file_paths.append(file_location)

    indexing_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "total": 100,
        "message": "Task queued",
    }

    thread = threading.Thread(target=run_indexing, args=(task_id, file_paths))
    thread.start()

    return {"task_id": task_id, "message": "File upload successful, indexing started."}


@router.get("/rag/progress/{task_id}")
async def get_indexing_progress(task_id: str):
    task = indexing_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@router.post("/rag/reload")
async def reload_rag_endpoint():
    if rag_service.reload():
        return {"message": "RAG service reloaded successfully."}
    raise HTTPException(
        status_code=500, detail="Failed to reload RAG service. Check server logs."
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_rag(request: ChatRequest):
    if not rag_service or not rag_service.qa_chain:
        raise HTTPException(
            status_code=503, detail="RAG service is not available.")

    try:
        rewritten_question = rewrite_query_with_openai(request.question)
        result = rag_service.qa_chain.invoke(rewritten_question)
        return ChatResponse(answer=result.get("result", "No answer found."), sources=[])
    except Exception as e:
        print(f"ERROR: RAG chat processing failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"An error occurred during chat processing: {e}"
        )
