# %%
import requests
import json
import google.generativeai as genai
from google.generativeai import types as gt
import os
from dotenv import load_dotenv

load_dotenv()

baseUrl = "http://localhost:3000"
url = "http://localhost:3000/issues.json?project_id=test-project"
headers = {
    "X-Redmine-API-Key": "7860f7b5a6597577420d79d87d584f06d17f1c95"
}

# %%
# 1. 拉取 Redmine 工单


def redmine_get_projects(api_key, url_base="http://localhost:3000"):
    url = f"{url_base}/projects.json"
    headers = {"X-Redmine-API-Key": api_key}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def redmine_get_issues(api_key, project_id, url_base="http://localhost:3000"):
    url = f"{url_base}/issues.json?project_id={project_id}"
    headers = {"X-Redmine-API-Key": api_key}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["issues"]

# 2. 格式化工单列表为字符串


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

# 通过comment反馈结果


def write_to_comment(id, redmine_api_key, url, response):
    issue_id = id
    comment = "AI分析" + response

    url = f"{url}/issues/{issue_id}.json"
    headers = {
        "X-Redmine-API-Key": redmine_api_key,
        "Content-Type": "application/json; charset=utf-8"
    }
    data = {
        "issue": {
            "notes": comment
        }
    }

    response = requests.put(
        url,
        data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers=headers
    )
    print(response.status_code)
    if response.headers.get("Content-Type", "").startswith("application/json"):
        print(response.json())
    else:
        print("不是JSON，原始内容如上")


# 通过wiki反映结果
def upsert_wiki_page(base_url, project_identifier, title, text, api_key, comment=""):
    from urllib.parse import quote
    url = f"{base_url}/projects/{project_identifier}/wiki/{quote(title)}.json"
    headers = {
        "X-Redmine-API-Key": api_key,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    payload = {"wiki_page": {"text": text, "comments": comment}}
    r = requests.put(url, data=json.dumps(
        payload, ensure_ascii=False).encode("utf-8"), headers=headers)
    print("PUT:", r.status_code, r.text or "<no body>")

    g = requests.get(url, headers=headers)
    print("GET:", g.status_code)
    if g.ok and g.headers.get("Content-Type", "").startswith("application/json"):
        page = g.json().get("wiki_page", {})
        return {
            "ok": True,
            "title": page.get("title", title),
            "version": page.get("version"),
            "browser_url": f"{base_url}/projects/{project_identifier}/wiki/{quote(title)}"
        }
    else:
        return {"ok": False, "status": g.status_code, "body": g.text}


# %%
res = redmine_get_projects(api_key=REDMINE_API_KEY)
print(res)

# %%
# 3. 获取 Redmine 工单并格式化
issues = redmine_get_issues(REDMINE_API_KEY, REDMINE_PROJECT_ID)
issues_str = format_redmine_issues_to_str(issues)
print("Formatted Redmine issues:")
print(issues_str)

# %%
# 5. 调用 Gemini 做 Redmine 工单分析
genai.configure(api_key=GEMINI_API_KEY)

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

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=(
        "你是资深项目管理顾问。基于输入的 Redmine 工单做可执行、可落地的建议；"
        "突出优先级、风险与排期，避免空话。"
    ),
    generation_config=gt.GenerationConfig(
        temperature=0.3,
        # response_mime_type="application/json",  # 直接产出 JSON，最稳
        max_output_tokens=4096,
    )
)

# 6. 获取 Gemini 分析结果
gemini_response = model.generate_content(prompt)

# %%
gemini_response_md = gemini_response.text

# %%
# 7. （可选）将 Gemini 分析结果写入本地文件
with open("redmine_gemini_analysis.txt", "w") as f:
    f.write(gemini_response_md)

# %%
write_to_comment(1, REDMINE_API_KEY, baseUrl, gemini_response_md)

# %%
info = upsert_wiki_page(
    base_url=baseUrl,
    project_identifier=REDMINE_PROJECT_ID,   # 例如 "testproject-redmine"
    title="AI_Report",
    text=gemini_response_md,
    api_key=REDMINE_API_KEY,
    comment="自动更新的 AI 项目分析报告"
)
print(info)
