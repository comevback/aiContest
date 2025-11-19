import os
from tqdm import tqdm  # ✅ 进度条
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# 路径
DATA_DIR = "data"
INDEX_DIR = "faiss_index"

# 1️⃣ 加载 embedding 模型（多语言，适合中英文）
embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")

# 2️⃣ 切分器
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

# 3️⃣ 预扫描所有 PDF，统计总 chunk 数（用于进度条）
file_list = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(".pdf")]
all_docs_info = []  # [(filename, chunks)]
total_chunks = 0
for filename in file_list:
    filepath = os.path.join(DATA_DIR, filename)
    loader = PyPDFLoader(filepath)
    docs = loader.load()
    chunks = splitter.split_documents(docs)
    all_docs_info.append((filename, chunks))
    total_chunks += len(chunks)

if total_chunks == 0:
    print("⚠️ data/ 目录下没有可处理的 PDF，或切分后为空。")
    exit(0)

print(f"📦 将处理 {len(file_list)} 个 PDF，共 {total_chunks} 个 chunk。")

# 4️⃣ 增量构建索引（分批 + 进度条 + 周期性保存）
batch_size = 64           # 每批处理的 chunk 数量
save_every_n_batches = 5  # 每 N 批保存一次

vectorstore = None
processed = 0
batch_texts, batch_metas = [], []

with tqdm(total=total_chunks, desc="Embedding & Indexing", unit="chunk") as pbar:
    for filename, chunks in all_docs_info:
        print(f"📘 正在处理: {filename}（{len(chunks)} 段）")

        for doc in chunks:
            batch_texts.append(doc.page_content)
            # metadata 保留文件名 + 原始 metadata
            meta = {"source": filename}
            if isinstance(doc.metadata, dict):
                meta.update(doc.metadata)
            batch_metas.append(meta)

            # 达到批量阈值 → 追加入库
            if len(batch_texts) >= batch_size:
                if vectorstore is None:
                    # 首批用 from_texts 创建
                    vectorstore = FAISS.from_texts(
                        batch_texts, embeddings, metadatas=batch_metas)
                else:
                    # 后续批次追加
                    vectorstore.add_texts(batch_texts, metadatas=batch_metas)

                processed += len(batch_texts)
                pbar.update(len(batch_texts))

                # 清空批缓存
                batch_texts, batch_metas = [], []

                # 周期性保存
                if (processed // batch_size) % save_every_n_batches == 0:
                    vectorstore.save_local(INDEX_DIR)
                    pbar.set_postfix_str(f"💾 已保存进度：{processed}/{total_chunks}")

        # 单个文件结束时也保存一次（稳妥）
        if vectorstore is not None:
            vectorstore.save_local(INDEX_DIR)

    # 处理最后不足一个 batch 的残余
    if batch_texts:
        if vectorstore is None:
            vectorstore = FAISS.from_texts(
                batch_texts, embeddings, metadatas=batch_metas)
        else:
            vectorstore.add_texts(batch_texts, metadatas=batch_metas)
        processed += len(batch_texts)
        pbar.update(len(batch_texts))
        batch_texts, batch_metas = [], []
        vectorstore.save_local(INDEX_DIR)

print(f"✅ 索引已创建并保存到 {INDEX_DIR}（共写入 {processed} 个 chunk）")
