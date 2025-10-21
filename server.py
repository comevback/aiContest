from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import os
from dotenv import load_dotenv
from redminelib import Redmine
from redminelib.exceptions import AuthError, ResourceNotFoundError
from openai import AzureOpenAI, APIConnectionError, APIStatusError
import re # Added for strip_markdown_fence
import csv
import io
from datetime import datetime, timedelta, date
import json

# Load environment variables from .env file
load_dotenv()

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = "2024-12-01-preview" # Updated API version
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o-mini" # Updated model name

if not REDMINE_URL or not REDMINE_API_KEY:
    raise ValueError("REDMINE_URL and REDMINE_API_KEY must be set in the .env file")

try:
    redmine = Redmine(REDMINE_URL, key=REDMINE_API_KEY)
    print(f"Successfully connected to Redmine at {REDMINE_URL}")
except AuthError:
    print("ERROR: Failed to authenticate with Redmine. Check your API key.")
    raise ValueError("Failed to authenticate with Redmine. Check your API key.")
except Exception as e:
    print(f"ERROR: Failed to connect to Redmine at {REDMINE_URL}: {e}")
    raise ValueError(f"Failed to connect to Redmine: {e}")

# Initialize Azure OpenAI client if credentials are provided
azure_openai_client = None
if AZURE_OPENAI_API_KEY:
    try:
        azure_openai_client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint="https://after-mgzd767o-eastus2.cognitiveservices.azure.com/" # Hardcoded as per user's working snippet
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
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class ProjectAnalysisRequest(BaseModel):
    project_id: str

def strip_markdown_fence(text: str) -> str:
    """
    去掉包裹在 ```markdown ... ``` 或 ``` ... ``` 之间的围栏。
    """
    if not text:
        return text
    text = text.strip()

    # 匹配以 ```markdown 或 ```md 或 ``` 开头的整块
    pattern = r"^```(?:markdown|md)?\s*([\s\S]*?)\s*```$"
    match = re.match(pattern, text, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # 如果不是整块 fenced code，但有部分包裹，也可以用替换去掉
    return re.sub(r"^```(?:markdown|md)?|```$", "", text, flags=re.MULTILINE).strip()

def analyze_redmine_issues_with_openai(issues_str: str) -> str:
    prompt = (
        "你是资深项目管理顾问，请根据以下 Redmine 工单列表，输出结构化的分析建议。\n"
        "请严格按照如下格式返回：\n"
        "项目建议：...\n"
        "排期管理建议：...\n"
        "人员分配建议：...\n"
        "要求：\n"
        "- 项目建议：针对整体项目进展、风险、优先级等提出建议。\n"
        "- 排期管理建议：对任务截止时间、进度延误、合理性等给出建议。\n"
        "- 人员分配建议：对当前人员分配合理性、负载、改进方向等给出建议。\n"
        "\n以下是 Redmine 工单列表：\n\n"
        + issues_str
    )

    example = (
        '''
        Analysis for AI Project
        ## 项目建议：
        鉴于当前有多个工单处于“新建”状态，并且优先级分级存在急迫性（如“修复紧急BUG1”），建议在项目整体进展上优先处理优先级高和紧急的任务，确保这些任务能在最短时间内得到解决。应定期评估工单进展，并适时调整任务优先级，识别潜在风险并制定应对措施，确保项目按计划推进。

        ## 排期管理建议：
        考虑到“修复紧急BUG1”任务的截止日期是2025年10月21日，建议立即着手执行。同时，尽管“开发新功能1”的截止日期是2025年10月24日，但由于该任务的优先级较高，建议在其后尽快开始，有效地避免由于时间紧迫导致的进度延误。对“support”任务，没有明确的截止时间，建议设定一个合理的时间框架，以推动其进展并确保资源的合理配置。

        ## 人员分配建议：
        目前所有工单均由同一负责人（Redmine Admin）负责，这可能导致负载过重和任务执行延迟。建议评估团队成员的能力和当前负载，合理分配工单，特别是在高优先级任务上进行适当的资源重新分配，以分担风险和压力，提升工作效率。可以引入团队其它成员，尤其是将“fix urgent bug 1”和“develop new feature 1”任务分配给不同的成员进行平行处理。
        '''
    )

    if not azure_openai_client:
        raise ValueError("Azure OpenAI client not initialized.")

    try:
        resp = azure_openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "请始终使用 Markdown 格式回答，必要时使用 ``` 代码块。 格式如：" + example},
                {"role": "user", "content": prompt}
            ]
        )
        open_ai_response = resp.choices[0].message.content
        openai_clean = strip_markdown_fence(open_ai_response)
        print("Raw OpenAI Response:\n" + open_ai_response) # Print raw response for debugging
        return openai_clean
    except Exception as e:
        print(f"Error calling Azure OpenAI API: {e}")
        raise e

@app.get("/api/projects")
async def get_projects():
    """Returns a list of projects from Redmine."""
    try:
        projects = redmine.project.all(limit=100) # Fetch up to 100 projects
        project_list = []
        for project in projects:
            project_list.append({"id": project.id, "name": project.name, "identifier": project.identifier})
        return {"projects": project_list}
    except Exception as e:
        print(f"ERROR: Failed to fetch projects from Redmine: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects from Redmine: {e}")

@app.get("/api/projects/{project_id}/issues")
async def get_issues(project_id: int):
    """Returns issues for a given project ID from Redmine."""
    try:
        issues = redmine.issue.filter(project_id=project_id, limit=100) # Fetch up to 100 issues
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
        raise HTTPException(status_code=404, detail="Project not found in Redmine")
    except Exception as e:
        print(f"ERROR: Failed to fetch issues for project {project_id} from Redmine: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch issues from Redmine: {e}")

@app.get("/api/projects/{project_id}/export/{format}")
async def export_data(project_id: int, format: str):
    """Exports project data in various formats."""
    try:
        issues = redmine.issue.filter(project_id=project_id, limit=100)
        if not issues:
            raise HTTPException(status_code=404, detail=f"No issues found for project {project_id}")

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
            raise HTTPException(status_code=400, detail="Invalid export format. Supported formats: json, csv, excel, pdf")
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found in Redmine")
    except Exception as e:
        print(f"ERROR: Failed to export data for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export data: {e}")

@app.post("/api/analyze")
async def analyze_project(request_body: ProjectAnalysisRequest):
    """Analyzes project issues using Azure OpenAI."""
    project_id = request_body.project_id

    if not azure_openai_client:
        print("ERROR: Azure OpenAI client not initialized. AI analysis cannot proceed.")
        raise HTTPException(status_code=500, detail="Azure OpenAI client not initialized. Check API key and endpoint.")

    try:
        print(f"Attempting to fetch issues for project {project_id} from Redmine...")
        project_issues = redmine.issue.filter(project_id=project_id, limit=100)
        if not project_issues:
            print(f"INFO: No issues found for project {project_id}. No analysis performed.")
            return {"analysis": f"No issues found for project {project_id}. No analysis performed."}

        issues_text = ""
        for issue in project_issues:
            issues_text += f"- ID: {issue.id}, Subject: {issue.subject}, Status: {issue.status.name}, Priority: {issue.priority.name}\n"
        
        print(f"Sending {len(project_issues)} issues to Azure OpenAI for analysis...")
        analysis_result = analyze_redmine_issues_with_openai(issues_text)
        print("AI analysis completed successfully.")
        return {"analysis": analysis_result}
    except ResourceNotFoundError:
        print(f"ERROR: Project {project_id} not found in Redmine during AI analysis.")
        raise HTTPException(status_code=404, detail="Project not found in Redmine")
    except (APIConnectionError, APIStatusError) as e:
        print(f"ERROR: Azure OpenAI API call failed: {e}")
        raise HTTPException(status_code=500, detail=f"Azure OpenAI API call failed: {e}")
    except Exception as e:
        print(f"ERROR: AI analysis failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")

@app.get("/api/projects/{project_id}/progress-prediction")
async def get_project_progress_prediction(project_id: int):
    """Returns overall project progress prediction data."""
    try:
        issues = redmine.issue.filter(project_id=project_id, limit=100)
        if not issues:
            raise HTTPException(status_code=404, detail=f"No issues found for project {project_id}")

        # Sort issues by creation date to establish a timeline
        issues_sorted_by_created = sorted(issues, key=lambda i: i.created_on)

        if not issues_sorted_by_created:
            return {"progress_data": [], "summary": "No issues to predict progress."}

        # Determine project start and end dates
        project_start_date = issues_sorted_by_created[0].created_on.date() if isinstance(issues_sorted_by_created[0].created_on, datetime) else issues_sorted_by_created[0].created_on
        
        all_due_dates = []
        for issue in issues:
            if hasattr(issue, 'due_date') and issue.due_date:
                if isinstance(issue.due_date, datetime):
                    all_due_dates.append(issue.due_date.date())
                elif isinstance(issue.due_date, date):
                    all_due_dates.append(issue.due_date)

        if not all_due_dates:
            project_end_date = project_start_date + timedelta(weeks=6) # Fallback if no due dates
        else:
            project_end_date = max(all_due_dates)

        today = datetime.now().date()

        # Adjust project_end_date if it's in the past
        if project_end_date < today:
            project_end_date = today + timedelta(weeks=2) # Extend prediction 2 weeks into future

        total_duration_days = (project_end_date - project_start_date).days
        if total_duration_days <= 0:
            total_duration_days = 1 # Avoid division by zero

        progress_data = []
        total_issues_count = len(issues)

        # Calculate weekly progress
        current_week_start = project_start_date
        week_num = 0
        while current_week_start <= project_end_date + timedelta(weeks=2): # Go two weeks beyond end for prediction
            week_num += 1
            week_end = current_week_start + timedelta(days=6)
            week_label = f"Week {week_num}"

            # Planned: Straight line from 0% at project_start_date to 100% at project_end_date
            days_passed_planned = (week_end - project_start_date).days
            planned_progress = min(100, max(0, (days_passed_planned / total_duration_days) * 100))

            # Actual: Issues completed by this week
            completed_by_week = [issue for issue in issues if 
                                 hasattr(issue.status, 'name') and 
                                 issue.status.name.lower() in ['closed', 'resolved', '完了', '解決'] and 
                                 (issue.updated_on.date() if isinstance(issue.updated_on, datetime) else issue.updated_on) <= week_end]
            actual_progress = (len(completed_by_week) / total_issues_count) * 100 if total_issues_count > 0 else 0
            actual_progress = round(actual_progress) if current_week_start <= today else None

            # Predicted: Simple extrapolation of current velocity
            predicted_progress_val = None
            if actual_progress is not None: # If we have actual data for this week
                predicted_progress_val = actual_progress
            elif progress_data: # Extrapolate from last known actual progress
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
                projected_progress = last_known_actual + avg_weekly_velocity * (week_num - (last_known_week_index + 1))
                predicted_progress_val = min(100, max(0, projected_progress))
            else:
                predicted_progress_val = 0 # Default if no actual data yet

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
            completed_issues_today = len([issue for issue in issues if hasattr(issue.status, 'name') and issue.status.name.lower() in ['closed', 'resolved', '完了', '解決'] and (issue.updated_on.date() if isinstance(issue.updated_on, datetime) else issue.updated_on) <= today])
            current_completion_rate = (completed_issues_today / total_issues_count) * 100

        current_planned_progress = 0
        days_passed_since_start = (today - project_start_date).days
        if days_passed_since_start > 0:
            current_planned_progress = min(100, max(0, (days_passed_since_start / total_duration_days) * 100))

        if current_completion_rate >= 100:
            summary_text = "项目已完成。"
        elif current_completion_rate >= current_planned_progress - 5: # Within 5% of planned
            summary_text = "项目按计划进行，预计将按时完成。"
        elif current_completion_rate < current_planned_progress - 5:
            summary_text = "项目进度落后于计划，存在延期风险，建议立即采取措施。"
        else:
            summary_text = "项目正在进行中，请持续关注进度。"

        return {"progress_data": progress_data, "summary": summary_text}
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found in Redmine")
    except Exception as e:
        print(f"ERROR: Failed to get progress prediction for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get progress prediction: {e}")

@app.get("/api/issues/{issue_id}/progress-prediction")
async def get_issue_progress_prediction(issue_id: int):
    """Returns progress prediction data for a single issue."""
    try:
        issue = redmine.issue.get(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found in Redmine")

        issue_start_date = issue.created_on.date() if isinstance(issue.created_on, datetime) else issue.created_on
        issue_due_date = None
        if hasattr(issue, 'due_date') and issue.due_date:
            issue_due_date = issue.due_date.date() if isinstance(issue.due_date, datetime) else issue.due_date
        
        if not issue_due_date:
            print(f"ERROR: Issue {issue_id} does not have a due date for prediction.")
            raise HTTPException(status_code=400, detail=f"Issue {issue_id} does not have a due date for prediction.")

        today = datetime.now().date()

        total_duration_days = (issue_due_date - issue_start_date).days
        if total_duration_days <= 0:
            total_duration_days = 1 # Avoid division by zero

        progress_data = []

        # Calculate daily progress for a finer granularity for single issue
        current_day = issue_start_date
        day_num = 0
        while current_day <= issue_due_date + timedelta(days=7): # Go one week beyond due date
            day_num += 1
            day_label = current_day.strftime("%Y-%m-%d")

            # Planned: Straight line from 0% at issue_start_date to 100% at issue_due_date
            days_passed_planned = (current_day - issue_start_date).days
            planned_progress = min(100, max(0, (days_passed_planned / total_duration_days) * 100))

            # Actual: 0% until updated_on (if status is not new), 100% if closed/resolved by current_day
            actual_progress = 0
            is_completed = hasattr(issue.status, 'name') and issue.status.name.lower() in ['closed', 'resolved', '完了', '解決']
            issue_updated_date = issue.updated_on.date() if hasattr(issue, 'updated_on') and isinstance(issue.updated_on, datetime) else issue.created_on.date()

            if is_completed and issue_updated_date <= current_day:
                actual_progress = 100
            elif issue_updated_date <= current_day and issue.status.name.lower() not in ['new', 'open', '新建', '开放']:
                # Simple linear interpolation for in-progress issues
                progress_since_start = (current_day - issue_start_date).days
                actual_progress = min(100, max(0, (progress_since_start / total_duration_days) * 100 * 0.8)) # Assume 80% of planned velocity
            
            # Predicted: Assume 100% by due date if not yet completed, otherwise follow actual
            predicted_progress = actual_progress
            if current_day > today and not is_completed:
                # Simple linear projection to 100% by due date
                days_remaining = (issue_due_date - current_day).days
                if days_remaining > 0:
                    predicted_progress = min(100, max(actual_progress, 100 - (days_remaining / total_duration_days) * 100))
                else:
                    predicted_progress = 100 # If past due, assume 100% for prediction

            progress_data.append({
                "week": day_label, # Using day_label for finer granularity
                "planned": round(planned_progress),
                "actual": round(actual_progress) if current_day <= today else None,
                "predicted": round(predicted_progress) if predicted_progress is not None else None,
            })
            current_day += timedelta(days=1)

        # Generate summary text for individual issue
        is_completed = hasattr(issue.status, 'name') and issue.status.name.lower() in ['closed', 'resolved', '完了', '解決']
        issue_updated_date = issue.updated_on.date() if hasattr(issue, 'updated_on') and isinstance(issue.updated_on, datetime) else issue.created_on.date()

        if is_completed:
            summary_text = f"工单 {issue.id} 已于 {issue_updated_date} 完成。"
        elif today > issue_due_date:
            summary_text = f"工单 {issue.id} 已逾期，原定截止日期为 {issue_due_date}。"
        elif predicted_progress >= 95:
            summary_text = f"工单 {issue.id} 预计将按时完成。"
        else:
            summary_text = f"工单 {issue.id} 正在进行中，预计完成日期为 {issue_due_date}。"

        return {"progress_data": progress_data, "summary": summary_text}
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Issue not found in Redmine")
    except HTTPException as e: # Catch HTTPException directly
        print(f"ERROR: Progress prediction for issue {issue_id} failed: {e.detail}")
        raise e # Re-raise the HTTPException
    except Exception as e:
        print(f"ERROR: Failed to get progress prediction for issue {issue_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get progress prediction for issue: {e}")
