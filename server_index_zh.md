# 服务器应用程序 (`server.py`) 索引

本文档提供了 `server.py` 应用程序的概述，详细介绍了其功能、核心组件和 API 端点。该服务器充当 Web 应用程序的后端，提供与 Redmine 的集成以及使用 Azure OpenAI 提供支持的 AI 驱动的检索增强生成 (RAG) 系统。

## 1. 简介

`server.py` 是一个 FastAPI 应用程序，主要有以下两个目的：

1.  **Redmine 集成：** 它连接到 Redmine 实例以获取项目数据、问题详细信息，并允许对项目状态进行 AI 驱动的分析，以及更新 Wiki 页面。
2.  **AI 驱动的知识库 (RAG)：** 它允许用户上传各种文档类型（PDF、Word、Excel、文本、Markdown）来构建知识库。然后，用户可以使用自然语言查询此知识库，系统会检索相关信息并使用 Azure OpenAI 生成答案。

## 2. 设置与配置

服务器依赖于环境变量，通常从 `.env` 文件加载。

**主要环境变量：**

*   `AZURE_OPENAI_API_KEY`: 您的 Azure OpenAI 服务 API 密钥。
*   `AZURE_OPENAI_API_VERSION`: Azure OpenAI 的 API 版本（例如，`2024-02-15-preview`）。
*   `AZURE_OPENAI_ENDPOINT`: 您的 Azure OpenAI 服务终结点 URL。
*   `AZURE_OPENAI_DEPLOYMENT_NAME`: 您的聊天模型的部署名称（例如，`gpt-4o-mini-xuxiang`）。
*   `AZURE_OPENAI_CHAT_DEPLOYMENT`: (可选) Langchain 聊天模型的特定部署名称，默认为 `AZURE_OPENAI_DEPLOYMENT_NAME`。

**目录结构：**

*   `data/`: 存储 RAG 系统上传的文档。
*   `faiss_index/`: 存储从文档生成的 FAISS 向量存储索引。

**依赖项：**

依赖项在 `requirements.txt` 中管理。请确保使用 `pip install -r requirements.txt` 进行安装。

## 3. 核心组件

*   **FastAPI：** 用于构建 RESTful API 的 Web 框架。
*   **Pydantic：** 用于数据验证和设置管理（例如，用于请求/响应正文的 `BaseModel`）。
*   **Redminelib：** 用于与 Redmine REST API 交互的 Python 库。
*   **Azure OpenAI：** 微软托管的 OpenAI 服务，提供用于分析、查询重写和 RAG 的 LLM 功能。
*   **Langchain：** 用于开发由语言模型驱动的应用程序的编排框架。
    *   **FAISS：** 用于密集向量的高效相似性搜索和聚类的库，用作向量存储。
    *   **HuggingFaceEmbeddings：** 使用 `intfloat/multilingual-e5-base` 等模型提供文本嵌入。
    *   **文档加载器：** 支持 `PyPDFLoader`、`TextLoader`、`UnstructuredWordDocumentLoader`、`UnstructuredExcelLoader`、`UnstructuredMarkdownLoader`。
    *   **RecursiveCharacterTextSplitter：** 用于将大型文档拆分为更小、语义上有意义的块。

## 4. RAG 系统详情

RAG 系统允许服务器根据私有文档集合回答问题。

### 4.1. 文档管理

*   **上传：** 用户可以通过 API 端点上传文档（PDF、DOCX、XLSX、TXT、MD）。这些文档存储在本地的 `data/` 目录中。
*   **删除：** 可以通过文件名删除文档，这会触发对剩余文档的完全重新索引。
*   **列表：** 一个端点提供所有当前存储文档的列表。

### 4.2. 索引过程

*   上传或删除文档时，会在 **后台线程** 中启动索引任务。
*   文档被加载，使用 `RecursiveCharacterTextSplitter` 拆分为块，然后使用 `HuggingFaceEmbeddings` 转换为数字向量嵌入。
*   这些嵌入存储在 `faiss_index/` 目录中的 **FAISS 向量存储** 中。
*   索引任务的进度在内存字典 (`indexing_tasks`) 中跟踪，并且可以通过 API 端点查询。
*   `RAGService` 类管理此向量存储和相关的 Langchain `RetrievalQA` 链的加载和重新加载。

### 4.3. 与 RAG 聊天

*   当用户提出问题时，服务器首先使用 Azure OpenAI **重写查询**，使其对向量数据库搜索更有效。
*   然后，重写的查询用于从 FAISS 索引中检索相关文档块。
*   这些检索到的块以及原始问题被馈送到 Azure OpenAI 聊天模型，通过 Langchain 的 `RetrievalQA` 链生成连贯的答案。

## 5. Redmine 集成

服务器提供通往 Redmine 的桥梁，允许前端应用程序与其交互。

### 5.1. 身份验证

Redmine API 调用需要 `X-Redmine-Url` 和 `X-Redmine-Api-Key` 请求头进行身份验证。辅助函数 `get_redmine_instance` 处理连接。

### 5.2. 项目与问题管理

*   **列出项目：** 从 Redmine 获取项目列表。
*   **获取问题：** 检索与特定 Redmine 项目 ID 相关的问题。
*   **导出数据：** 允许将项目问题导出为 JSON 或 CSV 格式。

### 5.3. AI 项目分析

*   `/api/analyze` 端点接收 Redmine `project_id`。
*   它获取该项目的所有问题。
*   然后将这些问题数据发送到 Azure OpenAI，并附带精心设计的提示，请求对项目、进度和人员配置建议进行结构化分析。
*   AI 的响应以 Markdown 格式返回。

### 5.4. Wiki 页面管理

*   `/api/projects/{project_identifier}/wiki` 端点允许更新（创建或修改）指定 Redmine 项目中的 Wiki 页面。
*   它使用 `PUT` 请求调用 Redmine 的 API，并处理各种错误场景（例如，未找到项目、身份验证失败）。

### 5.5. 进度预测

*   **项目进度 (`/api/projects/{project_id}/progress-prediction`)：**
    *   根据项目的创建日期、到期日期和状态更新，计算并返回整个项目的每周计划、实际和预测进度。
    *   包含总结文本，指示项目是否按计划进行、延迟或已完成。
*   **问题进度 (`/api/issues/{issue_id}/progress-prediction`)：**
    *   根据问题的创建日期、到期日期和更新日期，提供单个问题的每日计划、实际和预测进度。
    *   提供单个问题状态的总结文本。

## 6. API 端点摘要

| 方法 | 端点                                                  | 描述                                                 | 身份验证（Redmine Headers） |
| :----- | :-------------------------------------------------------- | :---------------------------------------------------------- | :------------------------------- |
| `GET`  | `/api/rag/documents`                                      | 列出 RAG 数据目录中的文档。                                 | 无                               |
| `DELETE`| `/api/rag/documents/{filename}`                           | 删除文档并触发重新索引。                                   | 无                               |
| `POST` | `/api/rag/upload`                                         | 上传文档到 RAG 数据目录进行索引。                            | 无                               |
| `GET`  | `/api/rag/progress/{task_id}`                             | 获取 RAG 索引任务的进度。                                   | 无                               |
| `POST` | `/api/rag/reload`                                         | 重新加载 RAG 服务（重新加载 FAISS 索引）。                    | 无                               |
| `POST` | `/api/chat`                                               | 与 RAG 系统聊天；根据文档回答问题。                         | 无                               |
| `GET`  | `/api/projects`                                           | 列出所有 Redmine 项目。                                     | 必填                             |
| `GET`  | `/api/projects/{project_id}/issues`                       | 列出特定 Redmine 项目的问题。                             | 必填                             |
| `GET`  | `/api/projects/{project_id}/export/{format}`              | 以 JSON 或 CSV 格式导出项目问题。                           | 必填                             |
| `POST` | `/api/analyze`                                            | 使用 Azure OpenAI 分析项目问题。                             | 必填                             |
| `POST` | `/api/projects/{project_identifier}/wiki`                 | 创建或更新 Redmine Wiki 页面。                              | 必填                             |
| `GET`  | `/api/projects/{project_id}/progress-prediction`          | 获取整个项目的进度预测数据。                                | 必填                             |
| `GET`  | `/api/issues/{issue_id}/progress-prediction`              | 获取单个问题的进度预测数据。                                | 必填                             |

## 7. 如何运行/使用

1.  **克隆仓库。**
2.  **安装依赖项：** `pip install -r requirements.txt`
3.  **在项目根目录创建 `.env` 文件** 并填写您的 Azure OpenAI 凭据。
4.  **启动服务器：** `uvicorn server:app --reload`
    *   `--reload` 标志对于开发很有用，因为它会在代码更改时重新启动服务器。
    *   FastAPI 通常可在 `http://127.0.0.1:8000` 访问。
5.  **访问 API 文档：** 运行后，您可以在 `http://127.0.0.1:8000/docs` (Swagger UI) 或 `http://127.00.1:8000/redoc` (ReDoc) 查看交互式 API 文档。

这份文档应该能帮助您理解 `server.py` 应用程序的结构和功能。