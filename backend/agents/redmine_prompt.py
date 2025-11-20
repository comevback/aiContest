# backend/agents/redmine_prompt.py
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def get_redmine_prompt():
    return ChatPromptTemplate.from_messages([
        ("system",
         "You are an AI Redmine Assistant.\n"
         "You can call tools to read or modify Redmine issues.\n"
         "Use JSON tool calling ONLY.\n"
         "If project name is given, you MUST find project_id automatically.\n"
         "If issue subject is given, you MUST find issue_id.\n"
         ),
        MessagesPlaceholder("messages"),
        ("assistant", "{agent_scratchpad}")
    ])
