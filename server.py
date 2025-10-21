from fastapi import FastAPI, HTTPException, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import os
from dotenv import load_dotenv
from redminelib import Redmine
from redminelib.exceptions import AuthError, ResourceNotFoundError
from openai import AzureOpenAI, APIConnectionError, APIStatusError
import re
import csv
import io
from datetime import datetime, timedelta, date
import json

# Load environment variables from .env file
load_dotenv()

# REDMINE_URL and REDMINE_API_KEY are now expected to be passed via headers

# Initialize Azure OpenAI client if credentials are provided
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o-mini"

azure_openai_client = None
if AZURE_OPENAI_API_KEY:
    try:
        azure_openai_client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint="https://after-mgzd767o-eastus2.cognitiveservices.azure.com/"
        )
        print("Successfully initialized Azure OpenAI client.")
    except Exception as e:
        print(f"WARNING: Failed to initialize Azure OpenAI client: {e}")
else:
    print("WARNING: Azure OpenAI API key not provided. AI analysis will be disabled.")

app = FastAPI()

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Redmine-Url", "X-Redmine-Api-Key"],
)


class ProjectAnalysisRequest(BaseModel):
    project_id: str


def strip_markdown_fence(text: str) -> str:
    """
    ```markdown ... ``` または ``` ... ``` で囲まれたフェンスを削除します。
    """
    if not text:
        return text
    text = text.strip()

    pattern = r"^```(?:markdown|md)?\s*([\s\S]*?)\s*```$"
    match = re.match(pattern, text, re.MULTILINE)
    if match:
        return match.group(1).strip()

    return re.sub(r"^```(?:markdown|md)?|```$", "", text, flags=re.MULTILINE).strip()


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


redmine_instance_cache = {}

# Helper function to get Redmine instance
def get_redmine_instance(redmine_url: str, redmine_api_key: str):
    if not redmine_url or not redmine_api_key:
        raise HTTPException(
            status_code=400, detail="Redmine URL and API Key are required.")

    # Create a unique key for the cache
    cache_key = f"{redmine_url}-{redmine_api_key}"

    if cache_key in redmine_instance_cache:
        return redmine_instance_cache[cache_key]

    try:
        redmine = Redmine(redmine_url, key=redmine_api_key)
        # Test connection to ensure credentials are valid
        redmine.auth() # This will raise AuthError if credentials are bad
        redmine_instance_cache[cache_key] = redmine # Store in cache
        return redmine
    except AuthError:
        raise HTTPException(
            status_code=401, detail="Failed to authenticate with Redmine. Check your API key.")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to Redmine: {e}")


@app.get("/api/projects")
async def get_projects(
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key")
):
    """Returns a list of projects from Redmine."""
    redmine = get_redmine_instance(x_redmine_url, x_redmine_api_key)
    try:
        projects = redmine.project.all(limit=100)
        project_list = []
        for project in projects:
            project_list.append(
                {"id": project.id, "name": project.name, "identifier": project.identifier})
        return {"projects": project_list}
    except Exception as e:
        print(f"ERROR: Failed to fetch projects from Redmine: {e}")
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
            issues_text += f"- ID: {issue.id}, Subject: {issue.subject}, Status: {issue.status.name}, Priority: {issue.priority.name}\n"

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
