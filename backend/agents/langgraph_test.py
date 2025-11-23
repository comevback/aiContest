
# To use SqliteSaver for checkpointing, you might need to install:
# pip install langgraph-checkpoint-sqlite

# backend/agents/langgraph_test.py
import os
import sys
import json
import operator
import sqlite3
from typing import Annotated, TypedDict, List, Union

from langchain_core.messages import (
    BaseMessage,
    ToolMessage,
    HumanMessage,
    AIMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import AzureChatOpenAI

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
# Note: SqliteSaver is now part of the 'langgraph-checkpoint-sqlite' package.
# Ensure it's installed: pip install langgraph-checkpoint-sqlite
from langgraph.checkpoint.sqlite import SqliteSaver

# Add project root to sys.path to allow absolute imports
project_root = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import Redmine tools
try:
    from backend.agents.redmine_tools import TOOLS
except ImportError:
    print("Error: Could not import Redmine tools. Make sure the path is correct.")
    print("Project Root:", project_root)
    print("Sys Path:", sys.path)
    TOOLS = []

# --- Enterprise Feature: Caching and Persistence ---
# Use SQLite for check-pointing to enable state persistence, retries, and rollbacks.
# By default, this uses an in-memory SQLite DB. To persist, change ":memory:" to a file path.
conn = sqlite3.connect(":memory:", check_same_thread=False)
memory = SqliteSaver(conn=conn)

# =========================================================================
# 1. Define Agent State
# =========================================================================


class AgentState(TypedDict):
    """
    The state of our graph.

    Attributes:
        messages: The list of messages that form the conversation history.
        is_final: A flag to indicate if the conversation should end.
        retry_count: A counter for tool execution retries.
    """
    messages: List[BaseMessage]
    is_final: bool
    retry_count: int

# =========================================================================
# 2. Define Nodes and Tools
# =========================================================================

# --- Enterprise Feature: Retry/Rollback and Smart Error Handling ---
# The tool node is wrapped to provide robust error handling and retry logic.
# If a tool fails, it will return a detailed error message to the LLM.


tool_node = ToolNode(TOOLS)

# Define the LLM for the agent. Using Azure OpenAI as an example.
# Ensure necessary environment variables are set:
# AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_DEPLOYMENT_NAME
try:
    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        openai_api_version=os.getenv("OPENAI_API_VERSION"),
        temperature=0,
        max_retries=3,  # LLM call retries
        model_kwargs={"seed": 42},  # for reproducibility
    )
    # Bind the tools to the LLM so it knows when to call them
    llm_with_tools = llm.bind_tools(TOOLS)
except Exception as e:
    print(
        f"Could not initialize AzureChatOpenAI. Please check your environment variables. Error: {e}")
    llm_with_tools = None


def agent_node(state: AgentState):
    """
    The main agent node. It calls the LLM to decide the next action.

    - If the LLM returns a tool call, it's passed to the tool_executor.
    - If the LLM returns a regular message, it's added to the state.
    - If the LLM believes the task is done, it should say so.
    """
    print("---AGENT NODE---")
    if not llm_with_tools:
        raise ValueError("LLM not initialized. Cannot proceed.")

    response = llm_with_tools.invoke(state["messages"])
    response.name = "agent"  # Assign a name for clarity in the graph
    # Reset retry count on successful agent call
    return {"messages": state["messages"] + [response], "retry_count": 0}


def tool_executor_node(state: AgentState):
    """
    Executes tools and handles errors with a retry mechanism.
    """
    print("---TOOL EXECUTOR NODE---")
    # The most recent message should be the AI's tool call.
    tool_call_message = state["messages"][-1]

    # --- Enterprise Feature: Tool Idempotency Check (Conceptual) ---
    # To make tools truly idempotent, they should be designed to handle being
    # called multiple times with the same input without changing the result
    # beyond the first call (e.g., creating a resource with the same name).
    # Here, we can add a basic check to prevent re-executing the *exact same*
    # tool call if it was the last action, though true idempotency lies in tool design.

    # Execute the tool call
    new_messages = []
    if isinstance(tool_call_message, AIMessage) and tool_call_message.tool_calls:
        for tool_call in tool_call_message.tool_calls:
            try:
                # Use the pre-built ToolNode to execute the call
                tool_output_raw = tool_node.invoke([tool_call])

                tool_output_messages = []
                # Guard against unexpected return types from ToolNode.
                # It should return a list of ToolMessages. On some errors, it might return a dict.
                if isinstance(tool_output_raw, list):
                    tool_output_messages = tool_output_raw
                elif isinstance(tool_output_raw, dict):
                    # Manually convert the error dict to a readable string to avoid JSON serialization errors
                    # on complex objects within the dict.
                    error_details = []
                    for key, value in tool_output_raw.items():
                        error_details.append(f"  - {key}: {str(value)}")
                    error_content = "Tool execution returned a dictionary (likely indicating an error):\n" + "\n".join(error_details)
                    tool_output_messages = [
                        ToolMessage(content=error_content, tool_call_id=tool_call['id'])
                    ]
                else:
                    # Raise a clear error if the return type is completely unexpected.
                    raise TypeError(f"Tool node returned an unexpected type: {type(tool_output_raw).__name__}. Value: {repr(tool_output_raw)}")

                # If the tool execution results in an empty list, create a generic message.
                if not tool_output_messages:
                    print(f"  INFO: Tool '{tool_call['name']}' executed but returned no output.")
                    tool_output_messages = [
                        ToolMessage(content="Tool executed successfully, but returned no explicit output.", tool_call_id=tool_call['id'])
                    ]
                
                new_messages.extend(tool_output_messages)

            except Exception as e:
                # --- Enterprise Feature: Smart Tool Error Hint ---
                # On failure, create a detailed error message for the LLM.
                # This includes the full traceback, which helps diagnose the root cause.
                import traceback
                tb_str = traceback.format_exc()
                error_message = (
                    f"Error executing tool '{tool_call['name']}' with args {tool_call['args']}.\n\n"
                    f"Exception Type: {type(e).__name__}\n"
                    f"Exception Details: {repr(e)}\n\n"
                    f"Full Traceback:\n{tb_str}\n\n"
                    "This error originated from the tool code, not the AI model. "
                    "Please check for issues like missing environment variables (e.g., REDMINE_URL, REDMINE_API_KEY), "
                    "network connectivity, or invalid tool arguments."
                )
                print(f"  ERROR: {error_message}")
                new_messages.append(ToolMessage(
                    content=error_message, tool_call_id=tool_call["id"]))

    return {"messages": state["messages"] + new_messages}


def summarizer_node(state: AgentState):
    """
    --- Enterprise Feature: Automatic Summarization ---
    If the conversation history gets too long, this node is called to summarize it.
    This keeps the context window manageable and focused.
    """
    print("---SUMMARIZER NODE---")
    if not llm:
        raise ValueError("LLM not initialized. Cannot proceed.")

    # --- FIX: Filter out tool calls and tool messages for summarization ---
    # The OpenAI API requires a clean history for summarization when the last message isn't a tool response.
    # We create a new list containing only human-readable messages.
    messages_for_summarization = []
    for msg in state["messages"]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            continue
        if isinstance(msg, ToolMessage):
            continue
        messages_for_summarization.append(msg)

    # Create a summary of the conversation
    prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="messages"),
        HumanMessage(content="Concisely summarize the preceding conversation and the current state of the task. "
                             "Focus on key outcomes, unresolved questions, and the next logical steps. "
                             "The goal is to condense the history for a new agent instance to take over without losing context.")
    ])
    # This chain uses the base LLM (without tools bound) to ensure no tool calls are made during summarization.
    summarizer_chain = prompt | llm

    summary_message = summarizer_chain.invoke({"messages": messages_for_summarization})
    summary_message.name = "summary"
    
    print(f"  Generated Summary: {summary_message.content}")

    # Replace the entire history with the new summary. This is the new condensed context.
    return {"messages": [summary_message]}


# =========================================================================
# 3. Define Graph and Edges
# =========================================================================

MAX_RETRIES = 3
MAX_MESSAGES_BEFORE_SUMMARY = 8


def should_continue(state: AgentState) -> str:
    """
    The main router. It decides where to go next based on the last message.
    """
    print("---ROUTER---")
    last_message = state["messages"][-1]

    # 1. First, prioritize executing tools if the agent requested them.
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        print("  décision: Agent requested tool call, executing.")
        return "execute_tools"

    # 2. THEN, check for summarization if the history is long.
    if len(state["messages"]) > MAX_MESSAGES_BEFORE_SUMMARY:
        print(
            f"   décision: History too long ({len(state['messages'])} messages), summarizing.")
        return "summarize"

    # 3. If the agent gives a final answer, end the conversation.
    if state.get("is_final") or not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        print("  décision: No tool calls, or final state reached. Ending.")
        return "end"

    # 4. Otherwise, default to continuing the agent loop
    return "continue"


def after_tool_execution(state: AgentState) -> str:
    """
    Router after tool execution to decide on retries.
    """
    print("---AFTER TOOL ROUTER---")
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and "error" in last_message.content.lower():
        if state.get("retry_count", 0) < MAX_RETRIES:
            print(
                f"  décision: Tool failed, retrying (Attempt {state['retry_count'] + 1}).")
            # Increment retry count and go back to the agent to re-plan.
            state["retry_count"] += 1
            return "continue"  # Back to agent node
        else:
            print("  décision: Tool failed, max retries reached. Ending.")
            state["is_final"] = True
            return "end"  # End the conversation

    print("  décision: Tool executed successfully, continuing agent loop.")
    return "continue"  # Back to agent node


# Create the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_executor_node)
workflow.add_node("summarizer", summarizer_node)

# Define edges
workflow.set_entry_point("agent")

# --- Enterprise Feature: Natural Language Decides Next Step ---
# Conditional routing forms the core of the agent's decision-making process.
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "execute_tools": "tools",
        "summarize": "summarizer",
        "end": "__end__",
        # This path is implicitly handled by the default "continue" logic in should_continue
    },
)

workflow.add_conditional_edges(
    "tools",
    after_tool_execution,
    {
        "continue": "agent",
        "end": "__end__",
    },
)

workflow.add_edge("summarizer", "agent")

# Compile the graph
# --- Enterprise Feature: Loop Protection (Recursion Limit) ---
# The recursion_limit prevents infinite loops.
app = workflow.compile(
    checkpointer=memory,
)

# =ree======================================================================
# 4. Run the Agent
# =========================================================================


def run_agent(query: str, thread_id: str):
    """
    Runs the agent with a given query and conversation thread ID.
    """
    if not llm_with_tools:
        print("Agent cannot run because LLM is not configured.")
        return

    # Configuration for the thread
    config = {"configurable": {"thread_id": thread_id}}

    # The initial state for a new conversation
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "is_final": False,
        "retry_count": 0,
    }

    print(f"\n===== Running Agent for Thread: {thread_id} =====\n")
    # Stream the events to see the agent's thought process
    try:
        for event in app.stream(initial_state, config, stream_mode="values"):
            # The event is the full state dictionary
            last_message = event["messages"][-1]

            if isinstance(last_message, AIMessage):
                if last_message.tool_calls:
                    print(f"LLM -> Tools: {last_message.tool_calls}")
                else:
                    print(f"LLM -> User: {last_message.content}")

            elif isinstance(last_message, ToolMessage):
                print(f"Tool -> LLM: {last_message.content}")

            print("-" * 50)

    except Exception as e:
        print(f"\nAn error occurred during agent execution: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("="*80)
    print(" Redmine LangGraph Agent Initialized ".center(80, "="))
    print("="*80)
    print("This is an enterprise-grade agent with features like:")
    print("- Caching and Persistence (in-memory SQLite)")
    print("- Tool error handling with automatic retries")
    print("- Automatic conversation summarization for long dialogues")
    print("- Loop protection and recursion limits")
    print("\nNOTE: Ensure Azure OpenAI environment variables are set.")
    print("Available tools:", [tool.name for tool in TOOLS])
    print("-" * 80)

    # --- Example Usage ---
    # Each unique thread_id maintains its own conversation state.

    # Example 1: A simple query to list projects
    thread_id_1 = "thread_list_projects"
    # run_agent("List all available Redmine projects.", thread_id_1)

    # Example 2: A multi-step query to find and update an issue
    thread_id_2 = "thread_find_and_update"
    query_2 = (
        "First, find a user named 'Admin'. Then, list all projects. "
        "After that, find issues in project 1 assigned to that user. "
        "Finally, pick one issue and add a note saying 'AI agent check-in'."
    )
    # run_agent(query_2, thread_id_2)

    # Example 3: A query designed to fail to test error handling
    thread_id_3 = "thread_error_test"
    # run_agent("Get details for issue 99999, which does not exist.", thread_id_3)

    print("\nTo run an example, uncomment one of the 'run_agent' calls in the main block.")
    print("Or, start an interactive session:")

    thread_id_interactive = "interactive-thread"
    print(
        f"\nStarting interactive session with thread_id='{thread_id_interactive}'...")
    while True:
        try:
            query = input("You: ")
            if query.lower() in ["exit", "quit"]:
                break
            run_agent(query, thread_id_interactive)
        except KeyboardInterrupt:
            print("\nExiting interactive session.")
            break
