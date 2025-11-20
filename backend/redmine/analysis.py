from fastapi import HTTPException
from pydantic import BaseModel
from openai import AzureOpenAI, APIConnectionError, APIStatusError
from backend.core.config import AZURE_OPENAI_DEPLOYMENT_NAME
from backend.redmine.client import get_redmine_instance
from backend.utils.text import strip_markdown_fence

# This client will need to be initialized and passed or imported from a centralized client module.
# For now, it's a placeholder. The actual client will be initialized in server.py and potentially passed down.
azure_openai_client: AzureOpenAI = None


def initialize_azure_openai_client(client: AzureOpenAI):
    global azure_openai_client
    azure_openai_client = client


class ProjectAnalysisRequest(BaseModel):
    project_id: str


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
        "\n以下は Redmine チケットの一覧です：\n\n" + issues_str
    )

    example = """
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
        """

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


async def analyze_project_logic(
    project_id: str, redmine_url: str, redmine_api_key: str
):
    """Analyzes project issues using Azure OpenAI."""
    redmine = get_redmine_instance(redmine_url, redmine_api_key)

    if not azure_openai_client:
        print("ERROR: Azure OpenAI client not initialized. AI analysis cannot proceed.")
        raise HTTPException(
            status_code=500,
            detail="Azure OpenAI client not initialized. Check API key and endpoint.",
        )

    try:
        print(
            f"Attempting to fetch issues for project {project_id} from Redmine...")
        project_issues = redmine.issue.filter(project_id=project_id, limit=100)
        if not project_issues:
            print(
                f"INFO: No issues found for project {project_id}. No analysis performed."
            )
            return {
                "analysis": f"No issues found for project {project_id}. No analysis performed."
            }

        issues_text = ""
        for issue in project_issues:
            # Safely get description and clean it up for the prompt
            description = (
                getattr(issue, "description", "説明なし")
                .replace("\n", " ")
                .replace("\r", "")
            )
            issues_text += f"- ID: {issue.id}, Subject: {issue.subject}, Status: {issue.status.name}, Priority: {issue.priority.name}, Description: {description}\n"

        print(
            f"Sending {len(project_issues)} issues to Azure OpenAI for analysis...")
        analysis_result = analyze_redmine_issues_with_openai(issues_text)
        print("AI analysis completed successfully.")
        return {"analysis": analysis_result}
    except APIConnectionError as e:
        print(f"ERROR: Azure OpenAI API connection failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Azure OpenAI API connection failed: {e}"
        )
    except APIStatusError as e:
        print(
            f"ERROR: Azure OpenAI API status error: {e.status_code} - {e.response}")
        raise HTTPException(
            status_code=500, detail=f"Azure OpenAI API error: {e.status_code} - {e.response}"
        )
    except Exception as e:
        print(f"ERROR: AI analysis failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")
