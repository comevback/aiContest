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

        lines.append("")

    return "\n".join(lines)


def strip_markdown_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return s


def parse_json_output(text: str) -> Any:
    cleaned = strip_markdown_code_fence(text.strip())
    return json.loads(cleaned)


# ---------------------------
# Planner Prompt
# ---------------------------
PLAN_PROMPT = ChatPromptTemplate.from_template("""
You are a planner.
You convert user instructions into a precise JSON execution plan.

You can use the following tools:

{tool_schema}

Rules:
- Output MUST be a JSON array.
- Each step MUST have: {{ "tool": "...", "args": {{...}} }}
- Use ONLY the tools listed above.
- Use correct required arguments.
- Produce EXACTLY the number of steps the user asks.
- NO explanation, NO extra text, ONLY valid JSON.

User request:
{input}
""")


planner_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    temperature=0,
)


# ---------------------------
# 错误分析：AI 解释错误
# ---------------------------
def analyze_error(tool_name: str, args: Dict[str, Any], error_text: str) -> str:
    prompt = f"""
A tool call failed in an Agent system.

Tool: {tool_name}
Args: {args}
Error: {error_text}

Please do:
1. Explain the error in friendly simple Chinese.
2. Suggest 2–4 possible next actions.
3. Ask the user what they want to do next.

Do NOT output JSON.
"""
    return planner_llm.invoke(prompt).content


# ---------------------------
# 决策 Prompt（方案 C：若用户表达不明确 → 询问具体值）
# ---------------------------
DECIDE_PROMPT = ChatPromptTemplate.from_template("""
You are an agent controller.

A tool call failed.

Tool: {tool_name}
Args: {args}

User replied:
"{user_reply}"

Your job:
Interpret the user's intention and generate an action in JSON.

JSON format:
{{
  "action": "retry" | "modify_args" | "skip" | "abort" | "continue" | "ask_user",
  "new_args": {{}} or null
}}

IMPORTANT RULES for "ask_user":
- If the user says vague things like "换个名字", "用别的名字", "重新弄", etc.,
  and does NOT provide a specific concrete name/identifier,
  then you MUST return:
  {{
    "action": "ask_user",
    "new_args": null
  }}
- DO NOT guess new identifiers.
- DO NOT create arguments yourself.
- Only when user clearly gives new name/identifier,
  then you may produce modify_args with exact new_args.

Output ONLY JSON. No explanation.
""")


def decide_next_action(user_reply: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    resp = planner_llm.invoke(
        DECIDE_PROMPT.format(
            user_reply=user_reply,
            tool_name=tool_name,
            args=args,
        )
    ).content
    return parse_json_output(resp)


# ---------------------------
# 执行计划：智能错误恢复（方案 C 完整实现）
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
            print(tool.run(tool_input))
            continue

        except Exception as e:
            error_text = str(e)
            print("\n🔥 工具执行失败！AI 正在分析原因...\n")

            # Step 1: AI 报告错误
            print(analyze_error(tool_name, args, error_text))

            # Step 2: 用户自然语言响应
            while True:
                user_reply = input("\n你的回答（请用自然语言描述你想怎么处理）：\n> ").strip()

                # Step 3: AI 判断下一步动作
                action_plan = decide_next_action(user_reply, tool_name, args)
                action = action_plan.get("action")
                new_args = action_plan.get("new_args")

                print(f"\n🤖 AI 决策: {action}, new_args = {new_args}")

                if action == "ask_user":
                    print("🤖 请提供具体的 name 与 identifier，例如：\n  名称：XXX\n  标识符：xxx-1")
                    continue  # 再问一次

                elif action == "modify_args":
                    updated = args.copy()
                    updated.update(new_args)
                    tool_input = json.dumps(updated, ensure_ascii=False)
                    print(f"🔄 使用新参数重试: {updated}")

                    try:
                        print(tool.run(tool_input))
                    except Exception as e2:
                        print(f"⚠ 重试失败: {e2}")
                    return  # ❗阻塞：结束整个计划

                elif action == "retry":
                    print("🔄 重试中...")
                    try:
                        print(tool.run(tool_input))
                    except Exception as e2:
                        print(f"⚠ 重试失败: {e2}")
                    return

                elif action == "skip":
                    print("➡ 跳过该步骤")
                    return

                elif action == "continue":
                    print("➡ 忽略错误，继续执行后续步骤")
                    break

                elif action == "abort":
                    print("🛑 执行终止")
                    exit()

                else:
                    print("⚠ 未知动作，已跳过")
                    return


# ---------------------------
# 主循环
# ---------------------------
print("Redmine Agent 启动成功（输入 exit 退出）")

while True:
    user = input("\n你：").strip()
    if user.lower() in {"exit", "quit"}:
        print("再见")
        break

    tool_schema = build_tools_schema(TOOLS)

    plan_msg = planner_llm.invoke(
        PLAN_PROMPT.format(
            input=user,
            tool_schema=tool_schema,
        )
    ).content

    print("\n生成的计划:")
    print(plan_msg)

    clean_plan = strip_markdown_code_fence(plan_msg)
    execute_plan(clean_plan)
