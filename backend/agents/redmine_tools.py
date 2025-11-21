# backend/agents/redmine_tools.py
import os
import json
from typing import Any
from langchain.tools import tool
from backend.redmine.client import get_redmine_instance
from backend.redmine.wiki import upsert_wiki_page
from backend.redmine.analysis import analyze_redmine_issues_with_openai

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")

# ============================================================
# Helper: Convert tool input to Python dict
# ============================================================


def parse_input(input_data: Any) -> dict:
    """Accept dict or JSON string. Always return a dict."""
    if input_data is None:
        return {}

    if isinstance(input_data, dict):
        return input_data

    if isinstance(input_data, str):
        input_data = input_data.strip()
        if input_data == "":
            return {}
        try:
            return json.loads(input_data)
        except Exception:
            return {"_raw": input_data}   # fallback

    return {"error": "Unsupported input type"}

# ============================================================
# Read-only tools
# ============================================================


@tool("list_projects")
def list_projects(input: Any) -> str:
    """List all Redmine projects."""
    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    projects = redmine.project.all(limit=200)
    return "\n".join([f"{p.id}: {p.name} ({p.identifier})" for p in projects])


@tool("get_project_issues")
def get_project_issues(input: Any) -> str:
    """Get issues for a project. Input: {"project_id": 1}"""
    data = parse_input(input)
    pid = data.get("project_id")

    if not pid:
        return "Error: project_id is required."

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issues = redmine.issue.filter(project_id=pid, limit=200)

    return "\n".join([f"{i.id}: {i.subject}" for i in issues])


@tool("analyze_project")
def analyze_project(input: Any) -> str:
    """Analyze issues by AI. Input: {"project_id": 1}"""
    data = parse_input(input)
    pid = data.get("project_id")

    if not pid:
        return "Error: project_id is required."

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issues = redmine.issue.filter(project_id=pid, limit=200)

    text = "\n".join([
        f"- {i.id} {i.subject}: {getattr(i, 'description', '')}"
        for i in issues
    ])

    return analyze_redmine_issues_with_openai(text)

# ============================================================
# Write tools (create/update/delete)
# ============================================================


@tool("create_issue")
def create_issue(input: Any) -> str:
    """Create issue. Input: {"project_id":1,"subject":"X","description":"Y"}"""
    data = parse_input(input)

    project_id = data.get("project_id")
    subject = data.get("subject")
    description = data.get("description", "")

    if not project_id or not subject:
        return "Error: project_id and subject are required."

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issue = redmine.issue.create(
        project_id=project_id,
        subject=subject,
        description=description
    )

    return f"Issue created: #{issue.id} {issue.subject}"


@tool("update_issue")
def update_issue(input: Any) -> str:
    """Update issue. Input: {"issue_id":10,"subject":"New"}"""
    data = parse_input(input)

    issue_id = data.get("issue_id")
    if not issue_id:
        return "Error: issue_id is required."

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issue = redmine.issue.get(issue_id)

    allowed = ["subject", "description",
               "priority_id", "status_id", "assigned_to_id"]
    changes = {k: v for k, v in data.items() if k in allowed}

    if not changes:
        return "No valid fields to update."

    issue.save(**changes)
    return f"Issue {issue_id} updated."


@tool("add_note")
def add_note(input: Any) -> str:
    """Add a note. Input: {"issue_id":10,"note":"xxx"}"""
    data = parse_input(input)

    issue_id = data.get("issue_id")
    note = data.get("note")

    if not issue_id or not note:
        return "Error: issue_id and note are required."

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issue = redmine.issue.get(issue_id)

    issue.notes = note
    issue.save()

    return f"Note added to issue {issue_id}."


@tool("update_wiki")
def update_wiki(input: Any) -> str:
    """Update wiki. Input: {"project_identifier":"x","title":"x","content":"x"}"""
    data = parse_input(input)

    return upsert_wiki_page(
        base_url=REDMINE_URL,
        project_identifier=data.get("project_identifier"),
        title=data.get("title"),
        text=data.get("content"),
        api_key=REDMINE_API_KEY,
    )


TOOLS = [
    list_projects,
    get_project_issues,
    analyze_project,
    create_issue,
    update_issue,
    add_note,
    update_wiki,
]
