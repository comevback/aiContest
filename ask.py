import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# === 加载环境变量 ===
load_dotenv()

INDEX_DIR = "faiss_index"
embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")

# === 加载索引 ===
vectorstore = FAISS.load_local(
    INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# === LLM（Azure OpenAI） ===
llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    temperature=0.2
)

qa = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)

print("💬 RAG 系统已启动，可以开始提问。输入 'exit' 退出。\n")
while True:
    query = input("🧠 请输入你的问题: ").strip()
    if query.lower() in ["exit", "quit"]:
        break
    result = qa.invoke(query)
    print("\n🤖 答案:", result["result"])
    print("\n📖 来源：")
    for i, doc in enumerate(result["source_documents"], 1):
        print(f"--- 片段{i} --- 来自 {doc.metadata.get('source')}")
        print(doc.page_content[:300], "...\n")
