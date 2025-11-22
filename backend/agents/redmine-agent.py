# backend/agents/redmine-agent.py
import os
import json
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.redmine_tools import TOOLS

load_dotenv()


# ---------------------------
# 工具 schema 构建（让 Planner 理解所有 tools）
# ---------------------------
def build_tools_schema(tools) -> str:
    """
    读取所有 tools 的 schema（参数结构、哪些 required、说明等），
    自动转换成 Planner 能理解的文字结构。
    """
    lines = []
    for t in tools:
        lines.append(f"Tool: {t.name}")
        lines.append(f"Description: {t.description}")

        # 兼容 Pydantic v1 / v2
        if hasattr(t.args_schema, "model_json_schema"):
            schema = t.args_schema.model_json_schema()
        else:
            schema = t.args_schema.schema()

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        lines.append("Arguments:")
        for arg_name, arg_info in properties.items():
            arg_type = arg_info.get("type", "unknown")
            is_required = "required" if arg_name in required else "optional"
            lines.append(f"  - {arg_name} ({arg_type}, {is_required})")

        lines.append("")  # 空行分隔工具

    return "\n".join(lines)


# ---------------------------
# 去掉 ```json 代码块，方便 json.loads
# ---------------------------
def strip_markdown_code_fence(s: str) -> str:
    """去掉 ```json 和 ``` 包裹的内容，让 json.loads 可以解析"""
    s = s.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        # 去掉第一行和最后一行
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return s


def parse_json_output(text: str) -> Any:
    """通用 JSON 解析（兼容 ```json 包裹的情况）"""
    cleaned = strip_markdown_code_fence(text.strip())
    return json.loads(cleaned)


# ---------------------------
# Planner Prompt：生成执行计划
# ---------------------------
PLAN_PROMPT = ChatPromptTemplate.from_template("""
You are a planner.
You convert user instructions into a precise JSON execution plan.

You can use the following tools:

{tool_schema}

Rules:
- Output MUST be a JSON array.
- Each step MUST have: {{"tool": "...", "args": {{...}}}}
- Use ONLY the tools listed above.
- Use correct required arguments. Optional arguments may be supplied if needed.
- Produce EXACTLY the number of steps the user asks.
- NO explanation, NO extra text, ONLY valid JSON.

User request:
{input}
""")


# ---------------------------
# Planner LLM（同时复用做错误分析）
# ---------------------------
planner_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    temperature=0,
)


# ---------------------------
# 错误分析：AI 向用户解释错误并给出建议
# ---------------------------
def analyze_error(tool_name: str, args: Dict[str, Any], error_text: str) -> str:
    prompt = f"""
A tool call failed in an Agent system.

Tool: {tool_name}
Args: {args}
Error: {error_text}

1. Explain in simple, friendly language what went wrong, so that a non-expert user can understand.
2. Suggest 2–4 reasonable next actions the user can take. (e.g., change identifier, retry, skip, stop, etc.)
3. End with a short question asking the user what they would like to do next.

Respond in natural language (e.g., Chinese), no JSON, no code fences.
"""
    resp = planner_llm.invoke(prompt)
    return resp.content


# ---------------------------
# 决策：AI 根据用户自然语言决定下一步动作
# ---------------------------
DECIDE_PROMPT = ChatPromptTemplate.from_template("""
You are an agent controller.

A previous tool call failed.

Tool: {tool_name}
Args: {args}

The user saw an explanation and suggestions about the error and then replied:

User reply:
"{user_reply}"

Now, interpret the user's intention and output an action plan in JSON.

The JSON MUST have the following structure:

{{
  "action": "string",          // e.g., "retry", "modify_args", "skip", "abort", "continue", or other reasonable action
  "new_args": {{}} or null     // updated arguments for the tool call, if the user wants to change something
}}

Rules:
- If the user wants to try again with the same parameters, use "action": "retry" and "new_args": null.
- If the user wants to change identifier or other arguments, use "action": "modify_args" and put the changed fields in "new_args".
- If the user wants to skip this step, use "action": "skip".
- If the user wants to stop everything, use "action": "abort".
- If the user wants to ignore this error and move on, use "action": "continue".
- You may also invent other reasonable actions if clearly requested by the user.

Output ONLY JSON. No explanation, no code fences.
""")


def decide_next_action(user_reply: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    resp = planner_llm.invoke(
        DECIDE_PROMPT.format(
            user_reply=user_reply,
            tool_name=tool_name,
            args=args,
        )
    )
    return parse_json_output(resp.content)


# ---------------------------
# 执行计划：依次调用 tools，带智能错误恢复
# ---------------------------
def execute_plan(plan: Any) -> None:
    if isinstance(plan, str):
        plan = parse_json_output(plan)

    for step in plan:
        tool_name = step["tool"]
        args = step["args"]
        tool = {t.name: t for t in TOOLS}[tool_name]

        tool_input = json.dumps(args, ensure_ascii=False)

        print(f"\n[EXEC] Calling tool: {tool_name} with {args}")

        try:
            result = tool.run(tool_input)
            print(result)

        except Exception as e:
            error_text = str(e)

            print("\n🔥 工具执行失败！AI 正在分析原因...\n")

            # 1. AI 解释错误 + 提出建议
            report = analyze_error(tool_name, args, error_text)
            print(report)

            # 2. 用户自然语言回复
            user_reply = input("\n你的回答（请用自然语言描述你想怎么处理）：\n> ").strip()

            # 3. AI 决定下一步动作
            try:
                action_plan = decide_next_action(user_reply, tool_name, args)
            except Exception as parse_err:
                print(f"\n⚠ 无法解析 AI 的决策（{parse_err}），跳过当前步骤。")
                continue

            action = action_plan.get("action", "").strip()
            new_args = action_plan.get("new_args", None)

            print(f"\n🤖 AI 决策: {action}, new_args = {new_args}")

            # 4. 根据 AI 决策执行
            if action == "retry":
                print("🔄 使用原参数重试...")
                try:
                    result = tool.run(tool_input)
                    print(result)
                except Exception as e2:
                    print(f"⚠ 重试仍然失败: {e2}")
                continue

            elif action == "modify_args":
                if isinstance(new_args, dict):
                    updated_args = args.copy()
                    updated_args.update(new_args)
                    tool_input = json.dumps(updated_args, ensure_ascii=False)
                    print(f"🔄 使用更新后的参数重试: {updated_args}")
                    try:
                        result = tool.run(tool_input)
                        print(result)
                    except Exception as e2:
                        print(f"⚠ 重试仍然失败: {e2}")
                else:
                    print("⚠ new_args 不是字典，无法修改参数，跳过此步骤。")
                continue

            elif action == "skip":
                print("➡ 跳过该步骤")
                continue

            elif action == "continue":
                print("➡ 忽略该错误，继续执行后续步骤")
                continue

            elif action == "abort":
                print("🛑 执行终止")
                break

            else:
                print(f"⚠ 未知动作 '{action}'，跳过该步骤")
                continue


# ---------------------------
# 主循环：用户输入 → Planner 生成计划 → 执行计划
# ---------------------------
print("Redmine Agent 启动成功（输入 exit 退出）")

while True:
    user = input("\n你：").strip()
    if user.lower() in {"exit", "quit"}:
        print("再见")
        break

    # 1. 构建工具 schema，让 Planner 理解所有 tools
    tool_schema = build_tools_schema(TOOLS)

    # 2. 生成执行计划（可能带 ```json 代码块）
    plan_msg = planner_llm.invoke(
        PLAN_PROMPT.format(
            input=user,
            tool_schema=tool_schema,
        )
    ).content

    print("\n生成的计划:")
    print(plan_msg)

    # 3. 清洗 markdown，解析 JSON
    clean_plan = strip_markdown_code_fence(plan_msg)

    # 4. 执行计划（带智能错误恢复）
    execute_plan(clean_plan)
