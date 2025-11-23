"""
Enterprise-style LangGraph Redmine agent (simplified & fixed version).

- Uses AzureChatOpenAI + Redmine TOOLS
- Uses LangGraph StateGraph with tool-calling loop
- No infinite loops (router with stop condition)
- No broken summarizer / checkpoint bugs
"""

import os
import json
from typing import TypedDict, List, Dict, Any, Optional

from dotenv import load_dotenv

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver

from backend.agents.redmine_tools import TOOLS

# ---------------------------------------------------------------------
# Environment & LLM
# ---------------------------------------------------------------------

load_dotenv()

# Base LLM
base_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    temperature=0,
)

# LLM with tools attached (for tool-calling)
tools_by_name: Dict[str, BaseTool] = {t.name: t for t in TOOLS}
llm_with_tools = base_llm.bind_tools(list(tools_by_name.values()))

# ---------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------


class AgentState(TypedDict):
    # Full conversation history (LangChain Message objects)
    messages: List[Any]

    # Pending tool call info (from last LLM step)
    pending_tool: Optional[str]
    pending_args: Dict[str, Any]
    pending_tool_call_id: Optional[str]

    # Tool execution result + error flag
    tool_result: Any
    error: Optional[str]

    # Whether this task is finished
    done: bool


# ---------------------------------------------------------------------
# Agent node: call LLM, decide whether to use tools
# ---------------------------------------------------------------------


def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    - Take conversation history from state["messages"]
    - Call LLM with tool support
    - If LLM emits tool_calls -> set pending_tool / args
    - If no tool_calls -> mark done=True
    """
    messages = state["messages"]

    # If already done, just return; router will send to END
    if state.get("done"):
        return {}

    # Call LLM with current conversation
    response: AIMessage = llm_with_tools.invoke(messages)

    # Append the AI message to history
    updates: Dict[str, Any] = {
        "messages": [response],
        "pending_tool": None,
        "pending_args": {},
        "pending_tool_call_id": None,
        "done": False,
    }

    # Check if tool_calls exist
    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        # Use the first tool_call
        tc = tool_calls[0]
        tool_name = tc["name"]
        tool_args = tc.get("args", {}) or {}
        tool_call_id = tc.get("id")

        updates["pending_tool"] = tool_name
        updates["pending_args"] = tool_args
        updates["pending_tool_call_id"] = tool_call_id
        # Not done yet; need to run the tool
        updates["done"] = False
    else:
        # No tool call → final answer
        updates["done"] = True

    return updates


# ---------------------------------------------------------------------
# Tool node: actually execute the tool
# ---------------------------------------------------------------------


def tool_node(state: AgentState) -> Dict[str, Any]:
    """
    - Reads pending_tool / pending_args from state
    - Executes the matching tool
    - Appends ToolMessage to conversation
    - Clears pending_tool
    """
    tool_name = state.get("pending_tool")
    args = state.get("pending_args") or {}
    call_id = state.get("pending_tool_call_id")

    if not tool_name:
        # Nothing to do
        return {
            "tool_result": None,
            "error": None,
        }

    if tool_name not in tools_by_name:
        err = f"Unknown tool: {tool_name}"
        return {
            "tool_result": None,
            "error": err,
            "messages": [
                ToolMessage(
                    content=err,
                    name=tool_name,
                    tool_call_id=call_id or "unknown_call_id",
                )
            ],
            "pending_tool": None,
            "pending_args": {},
            "pending_tool_call_id": None,
        }

    tool = tools_by_name[tool_name]

    try:
        print(f"[Tool] Calling {tool_name} with args: {args}")
        raw_result = tool.run(json.dumps(args, ensure_ascii=False))
        print("[Tool] Result:")
        print(raw_result)

        tool_msg = ToolMessage(
            content=str(raw_result),
            name=tool_name,
            tool_call_id=call_id or "unknown_call_id",
        )

        return {
            "messages": [tool_msg],
            "tool_result": raw_result,
            "error": None,
            "pending_tool": None,
            "pending_args": {},
            "pending_tool_call_id": None,
        }

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"[Tool ERROR] {err}")
        tool_msg = ToolMessage(
            content=err,
            name=tool_name,
            tool_call_id=call_id or "unknown_call_id",
        )
        # In a more advanced version, we could let the LLM handle this error
        return {
            "messages": [tool_msg],
            "tool_result": None,
            "error": err,
            "pending_tool": None,
            "pending_args": {},
            "pending_tool_call_id": None,
            "done": True,  # stop on error for now
        }


# ---------------------------------------------------------------------
# Router after agent: decide whether to call tools or end
# ---------------------------------------------------------------------


def agent_router(state: AgentState) -> str:
    """
    - If done=True → end
    - Else if pending_tool is set → go to tool node
    - Else → end (nothing more to do)
    """
    if state.get("done"):
        return "end"
    if state.get("pending_tool"):
        return "call_tool"
    return "end"


# ---------------------------------------------------------------------
# Build LangGraph workflow
# ---------------------------------------------------------------------


workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

# Start from agent
workflow.add_edge("__start__", "agent")

# After agent, either call tool or end
workflow.add_conditional_edges(
    "agent",
    agent_router,
    {
        "call_tool": "tools",
        "end": END,
    },
)

# After tool, always go back to agent (LLM sees tool result)
workflow.add_edge("tools", "agent")

# Use in-memory checkpoint (just for thread separation)
checkpointer = MemorySaver()

app = workflow.compile(checkpointer=checkpointer)

# ---------------------------------------------------------------------
# Helper for running in CLI
# ---------------------------------------------------------------------


def run_agent(user_input: str, thread_id: str = "interactive-thread") -> None:
    """
    Run one turn of the agent for a given user input.
    """
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_input)],
        "pending_tool": None,
        "pending_args": {},
        "pending_tool_call_id": None,
        "tool_result": None,
        "error": None,
        "done": False,
    }

    config = {
        "configurable": {"thread_id": thread_id},
    }

    print(f"\n===== Running Agent for Thread: {thread_id} =====")

    try:
        for event in app.stream(initial_state, config, stream_mode="values"):
            # event is a dict like {"agent": {...}} or {"tools": {...}}
            if "agent" in event:
                agent_state = event["agent"]
                # Print latest assistant message (if any)
                msgs = agent_state.get("messages") or []
                if msgs:
                    last_msg = msgs[-1]
                    if isinstance(last_msg, AIMessage):
                        print("\n[Assistant]:", last_msg.content)

            if "tools" in event:
                tool_state = event["tools"]
                if tool_state.get("error"):
                    print("\n[Tool ERROR]:", tool_state["error"])
                else:
                    print("\n[Tool OUTPUT]:")
                    print(tool_state.get("tool_result"))

        print("\n===== Done =====\n")

    except Exception as e:
        print("\nAn error occurred during agent execution:", e)
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------


if __name__ == "__main__":
    print("===================================================================")
    print("===================== Redmine LangGraph Agent =====================")
    print("===================================================================")
    print("This agent uses LangGraph + AzureChatOpenAI + Redmine tools.")
    print("It supports tool-calling with loop control and basic error handling.")
    print("NOTE: Ensure Azure OpenAI environment variables are set correctly.")
    print("-------------------------------------------------------------------")
    print("Available tools:", list(tools_by_name.keys()))
    print("-------------------------------------------------------------------")
    print("Type your request (or 'exit' to quit):")

    thread_id = "interactive-thread"

    while True:
        user = input("You: ").strip()
        if user.lower() in {"exit", "quit"}:
            print("Bye.")
            break
        if not user:
            continue

        run_agent(user, thread_id=thread_id)
