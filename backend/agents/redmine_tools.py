# backend/agents/redmine_tools.py
import os
import json
from langchain.tools import tool
from backend.redmine.client import get_redmine_instance
from backend.redmine.wiki import upsert_wiki_page
from backend.redmine.analysis import analyze_redmine_issues_with_openai

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")

# -----------------------
# Helper function
# -----------------------


def ensure_json(input_str: str) -> dict:
    """Make sure the tool input is valid JSON."""
    try:
        return json.loads(input_str)
    except Exception as e:
        return {"error": f"Invalid JSON input: {e}"}

# -----------------------
# Read tools
# -----------------------


@tool("list_projects")
def list_projects(input: str) -> str:
    """List all Redmine projects."""
    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    projects = redmine.project.all(limit=200)
    return "\n".join([f"{p.id}: {p.name} ({p.identifier})" for p in projects])


@tool("get_project_issues")
def get_project_issues(input: str) -> str:
    """Get issues for a project. Input JSON: {"project_id": 1}"""
    data = ensure_json(input)
    pid = data.get("project_id")

    if not pid:
        return "project_id is required"

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issues = redmine.issue.filter(project_id=pid, limit=200)

    return "\n".join([f"{i.id}: {i.subject}" for i in issues])


@tool("analyze_project")
def analyze_project(input: str) -> str:
    """Analyze project issues via AI. Input: {"project_id": 1}"""
    data = ensure_json(input)
    pid = data.get("project_id")
    if not pid:
        return "project_id is required"

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issues = redmine.issue.filter(project_id=pid, limit=200)

    text = ""
    for i in issues:
        desc = getattr(i, "description", "")
        text += f"- {i.id} {i.subject}: {desc}\n"

    return analyze_redmine_issues_with_openai(text)

# -----------------------
# Write tools
# -----------------------


@tool("create_issue")
def create_issue(input: str) -> str:
    """Create issue. Input: {"project_id":1,"subject":"X","description":"Y"}"""
    data = ensure_json(input)

    project_id = data.get("project_id")
    subject = data.get("subject")
    description = data.get("description", "")

    if not project_id or not subject:
        return "project_id and subject are required."

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issue = redmine.issue.create(
        project_id=project_id,
        subject=subject,
        description=description
    )

    return f"Issue created: #{issue.id} {issue.subject}"


@tool("update_issue")
def update_issue(input: str) -> str:
    """Update issue. Input: {"issue_id":10, "subject":"New"}"""
    data = ensure_json(input)

    issue_id = data.get("issue_id")
    if not issue_id:
        return "issue_id is required."

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issue = redmine.issue.get(issue_id)

    updatable = ["subject", "description",
                 "priority_id", "status_id", "assigned_to_id"]
    fields = {k: v for k, v in data.items() if k in updatable}

    issue.save(**fields)
    return f"Issue {issue_id} updated."


@tool("add_note")
def add_note(input: str) -> str:
    """Add note to issue. Input: {"issue_id": 10, "note": "xxx"}"""
    data = ensure_json(input)

    issue_id = data.get("issue_id")
    note = data.get("note")

    if not issue_id or not note:
        return "issue_id and note are required."

    redmine = get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)
    issue = redmine.issue.get(issue_id)

    issue.notes = note
    issue.save()

    return f"Note added to issue {issue_id}."


@tool("update_wiki")
def update_wiki(input: str) -> str:
    """Update wiki. Input: {"project_identifier":"x","title":"x","content":"x"}"""
    data = ensure_json(input)
    return upsert_wiki_page(
        base_url=REDMINE_URL,
        project_identifier=data["project_identifier"],
        title=data["title"],
        text=data["content"],
        api_key=REDMINE_API_KEY,
    )


# export tools list
TOOLS = [
    list_projects,
    get_project_issues,
    analyze_project,
    create_issue,
    update_issue,
    add_note,
    update_wiki,
]
