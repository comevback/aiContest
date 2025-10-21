from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import os
from dotenv import load_dotenv
from redminelib import Redmine
from redminelib.exceptions import AuthError, ResourceNotFoundError
from openai import AzureOpenAI, APIConnectionError, APIStatusError
import re  # Added for strip_markdown_fence

# Load environment variables from .env file
load_dotenv()

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"  # Updated API version
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o-mini"  # Updated model name

if not REDMINE_URL or not REDMINE_API_KEY:
    raise ValueError(
        "REDMINE_URL and REDMINE_API_KEY must be set in the .env file")

try:
    redmine = Redmine(REDMINE_URL, key=REDMINE_API_KEY)
    print(f"Successfully connected to Redmine at {REDMINE_URL}")
except AuthError:
    print("ERROR: Failed to authenticate with Redmine. Check your API key.")
    raise ValueError(
        "Failed to authenticate with Redmine. Check your API key.")
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
            # Hardcoded as per user's working snippet
            azure_endpoint=AZURE_OPENAI_ENDPOINT
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

# Mock Data (will be replaced by Redmine data where possible)
MOCK_PROGRESS_DATA = {
    1: [  # Project Alpha
        {"week": "Week 1", "planned": 20, "actual": 18, "predicted": 18},
        {"week": "Week 2", "planned": 40, "actual": 35, "predicted": 36},
        {"week": "Week 3", "planned": 60, "actual": 52, "predicted": 58},
        {"week": "Week 4", "planned": 80, "actual": 70, "predicted": 75},
        {"week": "Week 5", "planned": 100, "actual": None, "predicted": 88},
        {"week": "Week 6", "planned": 100, "actual": None, "predicted": 98},
    ],
    2: [  # Project Beta
        {"week": "Week 1", "planned": 15, "actual": 15, "predicted": 15},
        {"week": "Week 2", "planned": 30, "actual": 28, "predicted": 29},
        {"week": "Week 3", "planned": 45, "actual": 40, "predicted": 42},
        {"week": "Week 4", "planned": 60, "actual": None, "predicted": 55},
    ],
    3: [  # Project Gamma
        {"week": "Week 1", "planned": 25, "actual": 22, "predicted": 23},
        {"week": "Week 2", "planned": 50, "actual": 48, "predicted": 49},
        {"week": "Week 3", "planned": 75, "actual": None, "predicted": 70},
    ]
}


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
                {"role": "system",
                    "content": "请始终使用 Markdown 格式回答，必要时使用 ``` 代码块。 格式如：" + example},
                {"role": "user", "content": prompt}
            ]
        )
        open_ai_response = resp.choices[0].message.content
        openai_clean = strip_markdown_fence(open_ai_response)
        # Print raw response for debugging
        print("Raw OpenAI Response:\n" + open_ai_response)
        return openai_clean
    except Exception as e:
        print(f"Error calling Azure OpenAI API: {e}")
        raise e


@app.get("/api/projects")
async def get_projects():
    """Returns a list of projects from Redmine."""
    try:
        projects = redmine.project.all(limit=100)  # Fetch up to 100 projects
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
async def get_issues(project_id: int):
    """Returns issues for a given project ID from Redmine."""
    try:
        issues = redmine.issue.filter(
            project_id=project_id, limit=100)  # Fetch up to 100 issues
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
async def export_data(project_id: int, format: str):
    """Simulates exporting project data in various formats."""
    # In a real application, you would generate the actual file content
    # and return it with appropriate headers.
    time.sleep(1)  # Simulate work
    return {"message": f"Exported project {project_id} data in {format} format."}


@app.post("/api/analyze")
async def analyze_project(request_body: ProjectAnalysisRequest):
    """Analyzes project issues using Azure OpenAI."""
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
async def get_progress_prediction(project_id: int):
    """Returns mock progress prediction data for a given project ID."""
    progress_data = MOCK_PROGRESS_DATA.get(project_id, [])
    if not progress_data:
        raise HTTPException(
            status_code=404, detail="Progress data not found for this project")
    return {"progress_data": progress_data}
