# agent_chat_cli.py
import os
import sys
import datetime
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_community.agent_toolkits.load_tools import load_tools
from langchain.tools import tool
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ---------- 环境 ----------
load_dotenv()  # 需要 .env 提供 AZURE_* 与 OPENAI_API_VERSION

# ---------- 自定义工具 ----------


@tool("get_weather", description="Get today's mock weather for a city.")
def get_weather(city: str) -> str:
    data = {"Tokyo": "晴，25°C", "Beijing": "多云，28°C",
            "Akita": "小雨，22°C", "Osaka": "晴转多云，27°C"}
    today = datetime.date.today().strftime("%Y-%m-%d")
    return f"{today} {city} 天气：{data.get(city, '未找到天气数据')}"


# ---------- LLM ----------
llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0,
)

# ---------- 工具（官方 + 自定义） ----------
tools = load_tools(["llm-math"], llm=llm)  # 需要 pip install numexpr
tools.append(get_weather)

# ---------- Prompt（对话式） ----------
tool_desc = "\n".join(
    f"- {t.name}: {t.description or 'No description'}" for t in tools)
tool_names = ", ".join(t.name for t in tools)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful AI agent.\n"
     "You can use the following tools:\n{tools}\n\n"
     "Use this ReAct format when you need tools:\n"
     "Thought: reason about what to do\n"
     "Action: one of [{tool_names}]\n"
     "Action Input: the input to the action\n"
     "Observation: the result of the action\n\n"
     "When you can answer, end with:\n"
     "Final Answer: <your answer>"),
    MessagesPlaceholder("messages"),          # ← 对话历史
    ("assistant", "{agent_scratchpad}"),              # ← 用户提问
]).partial(tools=tool_desc, tool_names=tool_names)

# ---------- Planner + 执行器 ----------
planner = create_react_agent(llm=llm, tools=tools, prompt=prompt)
agent = AgentExecutor(agent=planner, tools=tools,
                      verbose=False, handle_parsing_errors=True)

# ---------- CLI 循环 ----------


def main():
    print("🔧 CLI Agent（输入 'exit' / 'quit' 结束，或 Ctrl+C）")
    history = []  # messages 历史
    while True:
        try:
            user = input("\n你：").strip()
            if user.lower() in {"exit", "quit"}:
                print("👋 再见！")
                break

            history.append({"role": "user", "content": user})

            # 执行（AgentExecutor 会自动管理 intermediate_steps）
            resp = agent.invoke({"messages": history})

            # ReAct 模式的最终答案在 output
            answer = resp.get("output")
            if not answer and "messages" in resp:
                answer = resp["messages"][-1].get("content", "")

            print(f"🤖：{answer}")

            # 把助手回复也加入历史
            history.append({"role": "assistant", "content": answer})

        except KeyboardInterrupt:
            print("\n👋 已退出。")
            break
        except Exception as e:
            print(f"⚠️ 出错：{e}", file=sys.stderr)


if __name__ == "__main__":
    main()
