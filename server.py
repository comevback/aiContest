import re
import os
import requests
import json
import google.generativeai as genai
from google.generativeai import types as gt
from openai import AzureOpenAI
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 加载环境变量
load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")
BASE_URL = "http://localhost:3000"  # 假设 Redmine 运行在本地3000端口

# 配置 Gemini
genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI()

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001",
                   "http://localhost:5173"],  # 允许 React 前端（假设在3001端口）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    project_id: str

# --- Redmine 和 Gemini 的核心逻辑函数 ---


def redmine_get_issues(api_key, project_id, url_base="http://localhost:3000"):
    url = f"{url_base}/issues.json?project_id={project_id}&status_id=*"
    headers = {"X-Redmine-API-Key": api_key}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("issues", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Redmine issues: {e}")
        return None


def format_redmine_issues_to_str(issues):
    lines = []
    for i in issues:
        subject = i.get("subject", "无标题")
        status = i.get("status", {}).get("name", "未知状态")
        priority = i.get("priority", {}).get("name", "无优先级")
        assignee = (i.get("assigned_to") or {}).get("name", "未分配")
        author = (i.get("author") or {}).get("name", "未知作者")
        start_date = i.get("start_date", "无开始日期")
        due_date = i.get("due_date", "无截止日期")
        created_on = i.get("created_on", "未知创建时间")
        updated_on = i.get("updated_on", "未知更新时间")
        desc = i.get("description", "无描述")
        lines.append(
            f"{subject} | 状态: {status} | 优先级: {priority} | 负责人: {assignee} | 作者: {author} | 开始: {start_date} | 截止: {due_date} | 创建: {created_on} | 更新: {updated_on} | 描述: {desc[:20]}..."
        )
    return "\n".join(lines)


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


def analyze_with_gemini(issues_str):
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

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=(
            "你是资深项目管理顾问。基于输入的 Redmine 工单做可执行、可落地的建议；"
            "突出优先级、风险与排期，避免空话。"
        ),
        generation_config=gt.GenerationConfig(
            temperature=0.3,
            max_output_tokens=4096,
        )
    )

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint="https://after-mgzd767o-eastus2.cognitiveservices.azure.com/",
        api_version="2024-12-01-preview"
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "请始终使用 Markdown 格式回答，必要时使用 ``` 代码块。 格式如：" + example},
            {"role": "user", "content": prompt}
        ]
    )

    try:
        # gemini_response = model.generate_content(prompt)
        open_ai_response = resp.choices[0].message.content
        openai_clean = strip_markdown_fence(open_ai_response)
        # print(gemini_response.text)
        print(open_ai_response)
        return openai_clean
    except Exception as e:
        print(f"Error calling API: {e}")
        return "调用 AI API 时出错。"

# --- API 端点 ---


def redmine_get_projects(api_key, url_base="http://localhost:3000"):
    url = f"{url_base}/projects.json"
    headers = {"X-Redmine-API-Key": api_key}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("projects", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Redmine projects: {e}")
        return None


@app.get("/api/projects")
async def get_projects():
    if not REDMINE_API_KEY:
        return {"error": "API keys not configured on the server."}

    projects = redmine_get_projects(REDMINE_API_KEY, BASE_URL)

    if projects is None:
        return {"error": "Failed to fetch projects from Redmine."}

    return {"projects": projects}


@app.post("/api/analyze")
async def analyze_project(request: AnalyzeRequest):
    if not REDMINE_API_KEY or not GEMINI_API_KEY:
        return {"error": "API keys not configured on the server."}

    issues = redmine_get_issues(REDMINE_API_KEY, request.project_id, BASE_URL)

    if issues is None:
        return {"error": f"Failed to fetch issues for project_id: {request.project_id}"}

    if not issues:
        return {"analysis": "在指定的项目中没有找到需要分析的工单。"}

    issues_str = format_redmine_issues_to_str(issues)
    analysis_result = analyze_with_gemini(issues_str)

    return {"analysis": analysis_result}


@app.get("/")
def read_root():
    return {"message": "Redmine Analysis Server is running."}

# --- 运行服务器的指令 ---
# 要运行此服务器, 请在终端中执行:
# pip install -r requirements.txt
# uvicorn server:app --reload --port 8000
