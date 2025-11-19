import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

DATA_DIR = "data"
INDEX_DIR = "faiss_index"

embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

# 加载现有索引
vectorstore = FAISS.load_local(
    INDEX_DIR, embeddings, allow_dangerous_deserialization=True)

# 选择新文档
filename = input("请输入要添加的 PDF 文件名（放在 data/ 目录下）: ").strip()
filepath = os.path.join(DATA_DIR, filename)
if not os.path.exists(filepath):
    print("❌ 文件不存在:", filepath)
    exit()

loader = PyPDFLoader(filepath)
docs = loader.load()
chunks = splitter.split_documents(docs)
texts = [doc.page_content for doc in chunks]
metas = [{"source": filename, **doc.metadata} for doc in chunks]

# 添加到索引
vectorstore.add_texts(texts, metadatas=metas)
vectorstore.save_local(INDEX_DIR)
print(f"✅ 已将 {filename} 添加到索引。")
