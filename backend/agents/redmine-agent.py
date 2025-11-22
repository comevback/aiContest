# backend/agents/redmine-agent.py
import os
import json
from dotenv import load_dotenv

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.redmine_tools import TOOLS

load_dotenv()

PLAN_PROMPT = ChatPromptTemplate.from_template("""
You are a planner.
Your only job is to convert user instructions into a JSON plan.

Available tools:
{tools}

Rules:
- The plan MUST be a JSON array.
- Each element must be: {{"tool": "...", "args": {{"key": "value"}}}}
- You must strictly follow user's number requirements.
- No text, no explanation. Output ONLY valid JSON.

User request:
{input}
""")


# planner LLM：只负责生成计划
planner_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    temperature=0,
)


def execute_plan(plan):
    import json

    if isinstance(plan, str):
        plan = plan.strip()

        # Handle code fences: ```json ... ```
        if plan.startswith("```"):
            # Split into: ['', 'json\n[...]\n', '']
            parts = plan.split("```")
            plan = parts[1]  # The middle part
            plan = plan.strip()

        # Remove leading "json" if LLM adds it
        if plan.startswith("json"):
            plan = plan[4:].strip()

        # Now parse the JSON
        plan = json.loads(plan)

    # Execute each step
    for step in plan:
        tool_name = step["tool"]
        args = step["args"]
        tool = {t.name: t for t in TOOLS}[tool_name]

        print(f"\n[EXEC] Calling tool: {tool_name} with {args}")
        result = tool.run(args)
        print(result)


print("🤖 Redmine Agent 启动成功（输入 exit 退出）")

tool_names = [t.name for t in TOOLS]

while True:
    user = input("\n你：").strip()
    if user.lower() in {"exit", "quit"}:
        print("👋 再见")
        break

    # 让 planner LLM 生成 JSON 计划
    plan_msg = planner_llm.invoke(
        PLAN_PROMPT.format(
            input=user,
            tools=tool_names
        )
    ).content

    print("\n📌 生成的计划:")
    print(plan_msg)

    # 执行 JSON 计划
    execute_plan(plan_msg)
