import os
import re
import threading
import uuid
from typing import Dict, List
from tqdm import tqdm

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

from backend.core.config import DATA_DIR, INDEX_DIR

# In-memory storage for indexing task progress
indexing_tasks: Dict[str, Dict] = {}


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
                indexing_tasks[self.task_id]["progress"] = progress
            self.buffer = ""  # Reset buffer

    def flush(self):
        pass


def run_indexing(task_id: str, file_paths: List[str]):
    """
    Runs the document indexing process for multiple file types in a background thread.
    Updates the global `indexing_tasks` dictionary with progress.
    """
    task = indexing_tasks[task_id]
    task["status"] = "processing"
    task["message"] = "Initializing..."

    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-base")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=100)

        task["message"] = "Loading and splitting documents..."
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
                    chunk.metadata["source"] = file_name
                all_chunks.extend(chunks)
                processed_files.append(file_name)

            except Exception as e:
                ignored_files.append(file_name)
                print(f"ERROR: Failed to process file {file_name}: {e}")

        if not all_chunks:
            task["status"] = "failed"
            task["message"] = (
                f"No content could be extracted. Processed {len(processed_files)}, ignored {len(ignored_files)} files."
            )
            return

        task["total"] = len(all_chunks)
        task["progress"] = 0
        task["message"] = f"Embedding {len(all_chunks)} document chunks..."

        vectorstore = None
        if os.path.exists(os.path.join(INDEX_DIR, "index.faiss")):
            vectorstore = FAISS.load_local(
                INDEX_DIR, embeddings, allow_dangerous_deserialization=True
            )

        batch_size = 32
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i: i + batch_size]
            if vectorstore is None and i == 0:
                vectorstore = FAISS.from_documents(batch, embeddings)
            elif vectorstore is not None:
                vectorstore.add_documents(batch)

            # Update progress
            progress_percent = min(
                100, int(((i + len(batch)) / len(all_chunks)) * 100))
            task["progress"] = progress_percent
            task["message"] = (
                f"Embedding documents... ({i+len(batch)}/{len(all_chunks)})"
            )

        if vectorstore:
            vectorstore.save_local(INDEX_DIR)

        task["status"] = "completed"
        task["progress"] = 100
        task["message"] = (
            f"Success! Indexed {len(all_chunks)} chunks from {len(processed_files)} files. Ignored {len(ignored_files)} files."
        )

    except Exception as e:
        task["status"] = "failed"
        task["message"] = f"An unexpected error occurred during indexing: {str(e)}"
        print(f"[Indexing Task {task_id}] Failed: {e}")
