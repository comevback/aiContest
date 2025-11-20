# backend/agents/redmine-agent.py
import os
from dotenv import load_dotenv

from langchain_openai import AzureChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor

from backend.agents.redmine_tools import TOOLS
from backend.agents.redmine_prompt import get_redmine_prompt

load_dotenv()

llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    temperature=0,
)

prompt = get_redmine_prompt()

agent = create_tool_calling_agent(
    llm=llm,
    tools=TOOLS,
    prompt=prompt,
)

executor = AgentExecutor(
    agent=agent,
    tools=TOOLS,
    verbose=True,
    handle_parsing_errors=True,
)

print("🤖 Redmine Agent 启动成功（输入 exit 退出）")
history = []

while True:
    user = input("\n你：").strip()
    if user.lower() in {"exit", "quit"}:
        print("👋 再见")
        break

    history.append({"role": "user", "content": user})
    resp = executor.invoke({"messages": history})
    answer = resp["messages"][-1]["content"]

    print(f"🤖：{answer}")
    history.append({"role": "assistant", "content": answer})
