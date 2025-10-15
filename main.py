# %%
from dotenv import load_dotenv
import os
from google import genai
from google.genai import types as gt
import requests

# %%
# 读取 .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_HOST = os.getenv("JIRA_HOST")
PROJECT_KEY = os.getenv("PROJECT_KEY")

# 初始化 Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

# %%
# 获取最近更新的 Jira 任务


def jira_get(path, params=None):
    url = f"{JIRA_HOST}{path}"
    r = requests.get(url, params=params, auth=(JIRA_USER, JIRA_TOKEN))
    r.raise_for_status()
    return r.json()


# %%
# 1. 从 Jira 拉取任务
issues = jira_get("/rest/api/3/search", params={
    "jql": f"project={PROJECT_KEY} ORDER BY updated DESC",
    "maxResults": 10,
    "fields": "summary,status,assignee,duedate,priority,created,updated"
})["issues"]

# %%
# 2. 格式化任务列表为字符串


def format_issues_to_str(issues):
    """
    将 Jira issues 转换成字符串，便于交给 AI 分析
    """
    lines = []
    for i in issues:
        f = i["fields"]

        key = i.get("key", "N/A")
        summary = f.get("summary", "无标题")
        status = f.get("status", {}).get("name", "未知状态")
        assignee = (f.get("assignee") or {}).get("displayName", "未分配")
        duedate = f.get("duedate", "无截止日期")
        priority = (f.get("priority") or {}).get("name", "无优先级")
        created = f.get("created", "未知时间")
        updated = f.get("updated", "未知时间")
        labels = ", ".join(f.get("labels", [])) or "无标签"
        parent = (f.get("parent") or {}).get("key", "无父任务")

        lines.append(
            f"{key} | {summary} | 状态: {status} | 优先级: {priority} | 负责人: {assignee} | 截止: {duedate} | 创建: {created} | 更新: {updated} | 标签: {labels} | 父任务: {parent}"
        )

    return "\n".join(lines)


issues_str = format_issues_to_str(issues)
print("Formatted issues:")
print(issues_str)

# %%
# 3. 调用 Gemini 做分析
prompt = (
    "你是资深项目管理顾问，请根据以下 Jira 任务列表，分析风险并提出对策：\n\n"
    + issues_str
)

print("\n=== Prompt to Gemini ===")
print(prompt)

# %%
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=gt.GenerateContentConfig(temperature=0.3)
)

# %%
# 4. 获取 Gemini 分析结果
gemini_response = resp.text
# print("=== AI 分析结果 ===")
# print(gemini_response)

# %%
# 5. 定义将结果返回 Jira 的函数


def jira_post(path, data):
    """通用 POST 函数"""
    url = f"{JIRA_HOST}{path}"
    r = requests.post(url, json=data, auth=(JIRA_USER, JIRA_TOKEN))
    r.raise_for_status()
    return r.json()

# 6. 执行添加评论的操作


def add_comment_to_jira(issue_key, comment_text):
    """将评论添加到指定的 Jira issue"""
    comment_endpoint = f"/rest/api/3/issue/{issue_key}/comment"

    # Jira API v3 需要使用 Atlassian Document Format
    comment_data = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": comment_text
                        }
                    ]
                }
            ]
        }
    }

    try:
        result = jira_post(comment_endpoint, comment_data)
        print(f"成功将评论添加到 issue {issue_key}。")
        return result
    except requests.exceptions.HTTPError as e:
        print(f"添加到 issue {issue_key} 失败: {e}")
        print(f"Response body: {e.response.text}")
        return None


# %%
# 将下面的 'BTS-6' 替换为您希望评论的真实 JIRA ISSUE KEY !!!
issue_to_comment = "BTS-6"
add_comment_to_jira(issue_to_comment, gemini_response)
