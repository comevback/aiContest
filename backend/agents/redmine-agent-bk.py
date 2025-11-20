# ================================================================
#                Redmine ToolCalling Agent  (FINAL VERSION)
# ================================================================

import os
from dotenv import load_dotenv

from backend.redmine.client import get_redmine_instance
from backend.redmine.wiki import upsert_wiki_page
from backend.redmine.analysis import analyze_redmine_issues_with_openai

from langchain_openai import AzureChatOpenAI
from langchain.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# ================================================================
#                       Load ENV
# ================================================================
load_dotenv()
REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")


# ================================================================
#                      Redmine Tools
# ================================================================

# --- IMPORTANT ---
# ToolCalling Agent 会传 dict => 所以不需要参数的工具必须完全无参数！

@tool("list_projects")
def list_projects() -> str:
    """List all accessible Redmine projects."""
    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    projects = redmine.project.all(limit=200)
    return "\n".join([
        f"{p.id}: {p.name} ({p.identifier})"
        for p in projects
    ])


@tool("get_project_issues", description="Get issues of a project. Input: {\"project_id\": 1}")
def get_project_issues(project_id: int) -> str:
    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issues = redmine.issue.filter(project_id=int(project_id), limit=200)
    return "\n".join([f"{i.id}: {i.subject}" for i in issues])


@tool("analyze_project", description="Analyze issues of a project. Input: {\"project_id\": 1}")
def analyze_project(project_id: int) -> str:
    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issues = redmine.issue.filter(project_id=int(project_id), limit=200)

    text = ""
    for i in issues:
        desc = getattr(i, "description", "").replace("\n", " ")
        text += f"- {i.id} {i.subject}: {desc}\n"

    return analyze_redmine_issues_with_openai(text)


@tool("update_wiki",
      description='Update wiki page. Input: {"project_identifier": "...", "title": "...", "content": "..."}')
def update_wiki(data: dict) -> str:
    result = upsert_wiki_page(
        base_url=REDMINE_URL,
        project_identifier=data["project_identifier"],
        title=data["title"],
        text=data["content"],
        api_key=REDMINE_API_KEY,
    )
    return str(result)


tools = [list_projects, get_project_issues, analyze_project, update_wiki]


# ================================================================
#                         Azure LLM
# ================================================================
llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),  # <-- 你要求的变量
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    temperature=0,
)


# ================================================================
#                         Prompt
# ================================================================
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a Redmine management AI agent.\n"
     "You can call tools when needed.\n"
     "Use JSON tool calling ONLY.\n"
     "Never guess input format.\n"),
    MessagesPlaceholder("messages"),
    ("assistant", "{agent_scratchpad}")
])


# ================================================================
#                     Create ToolCalling Agent
# ================================================================
agent = create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt,
)

executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
)


# ================================================================
#                         CLI LOOP
# ================================================================
print("🤖 Redmine ToolCalling Agent（输入 exit 退出）")
history = []

while True:
    user = input("\n你：").strip()
    if user.lower() in {"exit", "quit"}:
        print("👋 再见！")
        break

    history.append({"role": "user", "content": user})

    resp = executor.invoke({"messages": history})

    # ToolCalling agent 输出在 messages[-1]
    answer = resp["messages"][-1]["content"]

    print(f"🤖：{answer}")
    history.append({"role": "assistant", "content": answer})
