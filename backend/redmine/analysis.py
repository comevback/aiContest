from fastapi import HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from openai import AzureOpenAI, APIConnectionError, APIStatusError

from backend.core.config import AZURE_OPENAI_DEPLOYMENT_NAME
from backend.redmine.client import get_redmine_instance
from backend.utils.text import strip_markdown_fence

# -------------------------------------------------------------------
# Azure OpenAI Client：支持“外部注入 + 自动初始化”的双模式
# -------------------------------------------------------------------

azure_openai_client: AzureOpenAI = None   # 外部注入优先
_client_initialized = False               # 防止重复初始化


def initialize_azure_openai_client(client: AzureOpenAI):
    """
    Server 可以主动传入 client。
    一旦传入，就总是优先使用 server 的 client。
    """
    global azure_openai_client, _client_initialized
    azure_openai_client = client
    _client_initialized = True
    print("[INFO] Azure OpenAI client set from server.")


def get_or_create_azure_openai_client() -> AzureOpenAI:
    """
    优先用 server 注入的 client。
    如果没有，就自动从 .env 初始化一个。
    """
    global azure_openai_client, _client_initialized

    # 有 server 注入 → 直接用
    if _client_initialized and azure_openai_client is not None:
        return azure_openai_client

    # 没注入 → 自动初始化一次
    if azure_openai_client is None:
        print("[INFO] Initializing Azure OpenAI client from .env...")
        load_dotenv()

        try:
            azure_openai_client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            )
            _client_initialized = True
            print("[INFO] Azure OpenAI client initialized (fallback mode).")
        except Exception as e:
            print("[ERROR] Failed to initialize Azure OpenAI client:", e)
            azure_openai_client = None

    return azure_openai_client


class ProjectAnalysisRequest(BaseModel):
    project_id: str


def analyze_redmine_issues_with_openai(issues_str: str) -> str:
    client = get_or_create_azure_openai_client()

    if not client:
        raise ValueError("Azure OpenAI クライアントが初期化されていません。（server 也没传入）")

    prompt = (
        "あなたは経験豊富なプロジェクトマネジメントコンサルタントです。"
        "以下の Redmine チケット一覧に基づき、構造的で実行可能な分析提案を日本語で出力してください。\n\n"
        "次の形式に従ってください：\n"
        "## プロジェクトに関する提案：...\n"
        "## スケジュール管理に関する提案：...\n"
        "## 人員配置に関する提案：...\n\n"
        "以下は Redmine チケットの一覧です：\n\n" + issues_str
    )

    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "プロのPMとしてMarkdownで回答してください。"},
                {"role": "user", "content": prompt},
            ],
        )
        text = resp.choices[0].message.content
        return strip_markdown_fence(text)
    except Exception as e:
        print("Azure OpenAI API Error:", e)
        raise e


async def analyze_project_logic(project_id: str, redmine_url: str, redmine_api_key: str):
    client = get_or_create_azure_openai_client()

    if not client:
        raise HTTPException(500, "Azure OpenAI client not initialized.")

    redmine = get_redmine_instance(redmine_url, redmine_api_key)

    try:
        issues = redmine.issue.filter(project_id=project_id, limit=100)
        if not issues:
            return {"analysis": "No issues found."}

        issues_text = ""
        for issue in issues:
            desc = getattr(issue, "description", "説明なし").replace("\n", " ")
            issues_text += (
                f"- ID: {issue.id}, Subject: {issue.subject}, "
                f"Status: {issue.status.name}, Priority: {issue.priority.name}, "
                f"Description: {desc}\n"
            )

        analysis = analyze_redmine_issues_with_openai(issues_text)
        return {"analysis": analysis}

    except Exception as e:
        print("Project analysis failed:", e)
        raise HTTPException(500, str(e))
