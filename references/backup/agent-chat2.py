# agent_chat_fixed.py
import os
import datetime
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_community.agent_toolkits.load_tools import load_tools
from langchain.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

load_dotenv()


@tool("get_weather", description="Get today's mock weather for a city.")
def get_weather(city: str) -> str:
    data = {"Tokyo": "晴，25°C", "Beijing": "多云，28°C",
            "Akita": "小雨，22°C", "Osaka": "晴转多云，27°C"}
    today = datetime.date.today().strftime("%Y-%m-%d")
    return f"{today} {city} 天气：{data.get(city, '未找到天气数据')}"


llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0,
)

tools = load_tools(["llm-math"], llm=llm)
tools.append(get_weather)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful AI assistant. "
     "You can use the following tools when necessary:\n{tools}\n\n"
     "When you call a tool, follow the JSON function calling format."),
    MessagesPlaceholder("messages"),          # 用户历史消息
    ("assistant", "{agent_scratchpad}"),      # ReAct中间步骤
]).partial(tools="\n".join(f"- {t.name}: {t.description}" for t in tools))

# Step 1️⃣ 创建 Planner
planner = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)

# Step 2️⃣ 包装成 Executor
executor = AgentExecutor(
    agent=planner,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
)

print("🧰 CLI ToolCalling Agent（输入 'exit' / 'quit' 结束）")
history = []
while True:
    user = input("\n你：").strip()
    if user.lower() in {"exit", "quit"}:
        print("👋 再见！")
        break
    history.append({"role": "user", "content": user})
    resp = executor.invoke({"messages": history})
    answer = resp["messages"][-1]["content"]
    print(f"🤖：{answer}")
    history.append({"role": "assistant", "content": answer})
