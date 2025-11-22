# backend/agents/redmine_tools.py

import os
import json
from typing import Any, List, Optional

from langchain.tools import tool
from backend.agents.tool_guard import guard_tool

from backend.redmine.client import get_redmine_instance
from backend.redmine.wiki import upsert_wiki_page
from backend.redmine.analysis import analyze_redmine_issues_with_openai

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")


# ============================================================
# Helper: Convert tool input to Python dict
# ============================================================

def parse_input(input_data: Any) -> dict:
    """
    Accept dict or JSON string. Always return a dict.

    - If input is JSON string, parse it.
    - If input is empty string, return {}.
    - If cannot parse, put raw string as {"_raw": "..."}.
    """
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
            return {"_raw": input_data}

    return {"error": "Unsupported input type"}


def get_redmine():
    if not REDMINE_URL or not REDMINE_API_KEY:
        raise ValueError(
            "REDMINE_URL or REDMINE_API_KEY not set in environment.")
    return get_redmine_instance(REDMINE_URL, REDMINE_API_KEY)


# ============================================================
# Project tools
# ============================================================

@tool("list_projects")
@guard_tool("list_projects")
def list_projects(input: Any = None) -> str:
    """
    List all Redmine projects.

    Input: null or "{}"
    Output: "id: name (identifier)" lines.
    """
    redmine = get_redmine()
    projects = redmine.project.all(limit=200)
    return "\n".join([f"{p.id}: {p.name} ({p.identifier})" for p in projects])


@tool("get_project")
@guard_tool("get_project")
def get_project(input: Any = None) -> str:
    """
    Get project detail.

    Input JSON: {"project_id": 1} or {"identifier": "my-project"}
    """
    data = parse_input(input)
    redmine = get_redmine()

    project_id = data.get("project_id")
    identifier = data.get("identifier")

    if project_id:
        project = redmine.project.get(project_id)
    elif identifier:
        project = redmine.project.get(identifier)
    else:
        return "Error: project_id or identifier is required."

    fields = [
        f"id: {project.id}",
        f"name: {project.name}",
        f"identifier: {project.identifier}",
        f"description: {getattr(project, 'description', '')}",
        f"status: {getattr(project, 'status', '')}",
        f"is_public: {getattr(project, 'is_public', '')}",
    ]
    return "\n".join(fields)


@tool("create_project")
@guard_tool("create_project")
def create_project(input: Any = None) -> str:
    """
    Create a new project.

    Input JSON: {"name": "New Project", "identifier": "new-project"}
    """
    data = parse_input(input)
    redmine = get_redmine()

    project = redmine.project.new()
    project.name = data.get("name")
    project.identifier = data.get("identifier")

    if not project.name or not project.identifier:
        return "Error: name and identifier are required."

    project.save()
    return f"Created project: {project.name} (ID: {project.id})"

# ============================================================
# Issue tools (read)
# ============================================================


@tool("get_project_issues")
@guard_tool("get_project_issues")
def get_project_issues(input: Any = None) -> str:
    """
    Get issues for a project.

    Input JSON: {"project_id": 1, "limit": 200, "status_id": "*"}
    Only project_id is required.
    """
    data = parse_input(input)
    pid = data.get("project_id")

    if not pid:
        return "Error: project_id is required."

    limit = data.get("limit", 200)
    status_id = data.get("status_id", None)

    redmine = get_redmine()
    filter_kwargs = {"project_id": pid, "limit": limit}
    if status_id is not None:
        filter_kwargs["status_id"] = status_id

    issues = redmine.issue.filter(**filter_kwargs)

    return "\n".join([f"{i.id}: {i.subject}" for i in issues])


@tool("get_issue")
@guard_tool("get_issue")
def get_issue(input: Any = None) -> str:
    """
    Get single issue detail.

    Input JSON: {"issue_id": 10}
    """
    data = parse_input(input)
    issue_id = data.get("issue_id")
    if not issue_id:
        return "Error: issue_id is required."

    redmine = get_redmine()
    issue = redmine.issue.get(issue_id)

    lines = [
        f"id: {issue.id}",
        f"project_id: {issue.project.id}",
        f"subject: {issue.subject}",
        f"description: {getattr(issue, 'description', '')}",
        f"status: {issue.status.name}",
        f"priority: {issue.priority.name}",
        f"tracker: {issue.tracker.name}",
        f"author: {issue.author.name}",
        f"assigned_to: {getattr(issue, 'assigned_to', None) and issue.assigned_to.name}",
        f"start_date: {getattr(issue, 'start_date', '')}",
        f"due_date: {getattr(issue, 'due_date', '')}",
    ]
    return "\n".join(lines)


@tool("search_issues")
@guard_tool("search_issues")
def search_issues(input: Any = None) -> str:
    """
    Search issues with simple filters.

    Input JSON example:
    {
        "project_id": 1,
        "status_id": "*",
        "assigned_to_id": 5,
        "subject": "bug",
        "limit": 50
    }

    Only project_id or other fields are optional.
    """
    data = parse_input(input)
    redmine = get_redmine()

    kwargs = {}
    if "project_id" in data:
        kwargs["project_id"] = data["project_id"]
    if "status_id" in data:
        kwargs["status_id"] = data["status_id"]
    if "assigned_to_id" in data:
        kwargs["assigned_to_id"] = data["assigned_to_id"]
    if "subject" in data:
        kwargs["subject"] = data["subject"]
    kwargs["limit"] = data.get("limit", 100)

    issues = redmine.issue.filter(**kwargs)
    if not issues:
        return "No issues found."

    lines = []
    for i in issues:
        lines.append(
            f"{i.id}: {i.subject} "
            f"(status={i.status.name}, priority={i.priority.name}, "
            f"assigned_to={getattr(i, 'assigned_to', None) and i.assigned_to.name})"
        )
    return "\n".join(lines)


# ============================================================
# Issue tools (write)
# ============================================================

@tool("create_issue")
@guard_tool("create_issue")
def create_issue(input: Any = None) -> str:
    """
    Create issue.

    Input JSON:
    {
        "project_id": 1,
        "subject": "Title",
        "description": "optional",
        "tracker_id": 1,
        "priority_id": 2,
        "assigned_to_id": 5,
        "start_date": "2025-11-01",
        "due_date": "2025-11-10"
    }

    Required: project_id, subject
    """
    data = parse_input(input)

    project_id = data.get("project_id")
    subject = data.get("subject")
    if not project_id or not subject:
        return "Error: project_id and subject are required."

    redmine = get_redmine()

    create_kwargs = {
        "project_id": project_id,
        "subject": subject,
    }

    for field in [
        "description",
        "tracker_id",
        "priority_id",
        "assigned_to_id",
        "start_date",
        "due_date",
    ]:
        if field in data:
            create_kwargs[field] = data[field]

    issue = redmine.issue.create(**create_kwargs)
    return f"Issue created: #{issue.id} {issue.subject}"


@tool("update_issue")
@guard_tool("update_issue")
def update_issue(input: Any = None) -> str:
    """
    Update issue basic fields.

    Input JSON:
    {
        "issue_id": 10,
        "subject": "New title",
        "description": "New desc",
        "priority_id": 3,
        "status_id": 2,
        "assigned_to_id": 5,
        "start_date": "2025-11-01",
        "due_date": "2025-11-10"
    }

    issue_id required. Only provided fields are updated.
    """
    data = parse_input(input)
    issue_id = data.get("issue_id")
    if not issue_id:
        return "Error: issue_id is required."

    redmine = get_redmine()
    issue = redmine.issue.get(issue_id)

    allowed = [
        "subject",
        "description",
        "priority_id",
        "status_id",
        "assigned_to_id",
        "start_date",
        "due_date",
    ]
    changes = {k: v for k, v in data.items() if k in allowed}

    if not changes:
        return "No valid fields to update."

    issue.save(**changes)
    return f"Issue {issue_id} updated."


@tool("delete_issue")
@guard_tool("delete_issue")
def delete_issue(input: Any = None) -> str:
    """
    Delete issue.

    Input JSON: {"issue_id": 10}
    """
    data = parse_input(input)
    issue_id = data.get("issue_id")
    if not issue_id:
        return "Error: issue_id is required."

    redmine = get_redmine()
    issue = redmine.issue.get(issue_id)
    issue.delete()
    return f"Issue {issue_id} deleted."


@tool("set_issue_status")
@guard_tool("set_issue_status")
def set_issue_status(input: Any = None) -> str:
    """
    Set issue status.

    Input JSON:
    {
        "issue_id": 10,
        "status_id": 3
    }

    (status_id 由 Redmine 配置决定，如 Open / In Progress / Closed 等)
    """
    data = parse_input(input)
    issue_id = data.get("issue_id")
    status_id = data.get("status_id")

    if not issue_id or status_id is None:
        return "Error: issue_id and status_id are required."

    redmine = get_redmine()
    issue = redmine.issue.get(issue_id)
    issue.save(status_id=status_id)
    return f"Issue {issue_id} status set to {status_id}."


@tool("assign_issue")
@guard_tool("assign_issue")
def assign_issue(input: Any = None) -> str:
    """
    Assign issue to a user.

    Input JSON:
    {
        "issue_id": 10,
        "assigned_to_id": 5
    }
    """
    data = parse_input(input)
    issue_id = data.get("issue_id")
    assigned_to_id = data.get("assigned_to_id")

    if not issue_id or not assigned_to_id:
        return "Error: issue_id and assigned_to_id are required."

    redmine = get_redmine()
    issue = redmine.issue.get(issue_id)
    issue.save(assigned_to_id=assigned_to_id)
    return f"Issue {issue_id} assigned to user {assigned_to_id}."


@tool("set_issue_priority")
@guard_tool("set_issue_priority")
def set_issue_priority(input: Any = None) -> str:
    """
    Set issue priority.

    Input JSON:
    {
        "issue_id": 10,
        "priority_id": 4
    }
    """
    data = parse_input(input)
    issue_id = data.get("issue_id")
    priority_id = data.get("priority_id")

    if not issue_id or priority_id is None:
        return "Error: issue_id and priority_id are required."

    redmine = get_redmine()
    issue = redmine.issue.get(issue_id)
    issue.save(priority_id=priority_id)
    return f"Issue {issue_id} priority set to {priority_id}."


@tool("set_issue_dates")
@guard_tool("set_issue_dates")
def set_issue_dates(input: Any = None) -> str:
    """
    Set issue start and due dates.

    Input JSON:
    {
        "issue_id": 10,
        "start_date": "2025-11-01",
        "due_date": "2025-11-10"
    }
    """
    data = parse_input(input)
    issue_id = data.get("issue_id")
    if not issue_id:
        return "Error: issue_id is required."

    redmine = get_redmine()
    issue = redmine.issue.get(issue_id)

    changes = {}
    if "start_date" in data:
        changes["start_date"] = data["start_date"]
    if "due_date" in data:
        changes["due_date"] = data["due_date"]

    if not changes:
        return "No dates provided."

    issue.save(**changes)
    return f"Issue {issue_id} dates updated."


@tool("add_note")
@guard_tool("add_note")
def add_note(input: Any = None) -> str:
    """
    Add a note to issue.

    Input JSON:
    {
        "issue_id": 10,
        "note": "some comment"
    }
    """
    data = parse_input(input)

    issue_id = data.get("issue_id")
    note = data.get("note")

    if not issue_id or not note:
        return "Error: issue_id and note are required."

    redmine = get_redmine()
    issue = redmine.issue.get(issue_id)

    issue.notes = note
    issue.save()

    return f"Note added to issue {issue_id}."


# ============================================================
# User tools
# ============================================================

@tool("list_users")
@guard_tool("list_users")
def list_users(input: Any = None) -> str:
    """
    List users.

    Input JSON (optional):
    {
        "limit": 100
    }
    """
    data = parse_input(input)
    limit = data.get("limit", 100)

    redmine = get_redmine()
    users = redmine.user.all(limit=limit)

    return "\n".join([f"{u.id}: {u.login} ({u.firstname} {u.lastname})" for u in users])


@tool("get_user")
@guard_tool("get_user")
def get_user(input: Any = None) -> str:
    """
    Get user detail.

    Input JSON: {"user_id": 5}
    """
    data = parse_input(input)
    user_id = data.get("user_id")
    if not user_id:
        return "Error: user_id is required."

    redmine = get_redmine()
    u = redmine.user.get(user_id)
    lines = [
        f"id: {u.id}",
        f"login: {u.login}",
        f"name: {u.firstname} {u.lastname}",
        f"mail: {u.mail}",
    ]
    return "\n".join(lines)


@tool("find_user_by_name")
@guard_tool("find_user_by_name")
def find_user_by_name(input: Any = None) -> str:
    """
    Find users by name substring.

    Input JSON: {"name": "Admin"}
    """
    data = parse_input(input)
    name = data.get("name")
    if not name:
        return "Error: name is required."

    redmine = get_redmine()
    users = redmine.user.filter(name=name, status=1)
    if not users:
        return "No active users found."

    return "\n".join([f"{u.id}: {u.login} ({u.firstname} {u.lastname})" for u in users])


# ============================================================
# Project member tools
# ============================================================

@tool("list_project_members")
@guard_tool("list_project_members")
def list_project_members(input: Any = None) -> str:
    """
    List project members.

    Input JSON: {"project_id": 1}
    """
    data = parse_input(input)
    project_id = data.get("project_id")
    if not project_id:
        return "Error: project_id is required."

    redmine = get_redmine()
    memberships = redmine.project_membership.filter(project_id=project_id)

    if not memberships:
        return "No members found."

    lines = []
    for m in memberships:
        user = m.user
        roles = ", ".join([r.name for r in m.roles])
        lines.append(
            f"{user.id}: {user.name} (roles: {roles}, membership_id={m.id})")
    return "\n".join(lines)


# ============================================================
# Wiki tools
# ============================================================

@tool("update_wiki")
@guard_tool("update_wiki")
def update_wiki(input: Any = None) -> str:
    """
    Create or update wiki page via helper.

    Input JSON:
    {
        "project_identifier": "my-project",
        "title": "Home",
        "content": "text..."
    }
    """
    data = parse_input(input)

    return upsert_wiki_page(
        base_url=REDMINE_URL,
        project_identifier=data.get("project_identifier"),
        title=data.get("title"),
        text=data.get("content"),
        api_key=REDMINE_API_KEY,
    )


@tool("get_wiki_page")
@guard_tool("get_wiki_page")
def get_wiki_page(input: Any = None) -> str:
    """
    Get wiki page content.

    Input JSON:
    {
        "project_identifier": "my-project",
        "title": "Home"
    }
    """
    data = parse_input(input)
    project_identifier = data.get("project_identifier")
    title = data.get("title")
    if not project_identifier or not title:
        return "Error: project_identifier and title are required."

    redmine = get_redmine()
    page = redmine.wiki_page.get(f"{project_identifier}/{title}")
    return getattr(page, "text", "")


@tool("list_wiki_pages")
@guard_tool("list_wiki_pages")
def list_wiki_pages(input: Any = None) -> str:
    """
    List wiki pages of a project.

    Input JSON: {"project_identifier": "my-project"}
    """
    data = parse_input(input)
    project_identifier = data.get("project_identifier")
    if not project_identifier:
        return "Error: project_identifier is required."

    redmine = get_redmine()
    pages = redmine.wiki_page.all(project_id=project_identifier)
    return "\n".join([p.title for p in pages])


@tool("delete_wiki_page")
@guard_tool("delete_wiki_page")
def delete_wiki_page(input: Any = None) -> str:
    """
    Delete a wiki page.

    Input JSON:
    {
        "project_identifier": "my-project",
        "title": "Home"
    }
    """
    data = parse_input(input)
    project_identifier = data.get("project_identifier")
    title = data.get("title")
    if not project_identifier or not title:
        return "Error: project_identifier and title are required."

    redmine = get_redmine()
    page = redmine.wiki_page.get(f"{project_identifier}/{title}")
    page.delete()
    return f"Wiki page '{title}' deleted from project '{project_identifier}'."


# ============================================================
# Time entry tools
# ============================================================

@tool("list_time_entries")
@guard_tool("list_time_entries")
def list_time_entries(input: Any = None) -> str:
    """
    List time entries.

    Input JSON example:
    {
        "project_id": 1,
        "issue_id": 10,
        "limit": 100
    }
    All fields optional.
    """
    data = parse_input(input)
    redmine = get_redmine()

    kwargs = {}
    if "project_id" in data:
        kwargs["project_id"] = data["project_id"]
    if "issue_id" in data:
        kwargs["issue_id"] = data["issue_id"]
    kwargs["limit"] = data.get("limit", 100)

    entries = redmine.time_entry.filter(**kwargs)
    if not entries:
        return "No time entries found."

    lines = []
    for t in entries:
        lines.append(
            f"{t.id}: user={t.user.name}, project={t.project.name}, "
            f"issue={getattr(t, 'issue', None) and t.issue.id}, "
            f"hours={t.hours}, spent_on={t.spent_on}, comments={t.comments}"
        )
    return "\n".join(lines)


@tool("add_time_entry")
@guard_tool("add_time_entry")
def add_time_entry(input: Any = None) -> str:
    """
    Add a time entry.

    Input JSON:
    {
        "project_id": 1,
        "issue_id": 10,
        "hours": 1.5,
        "spent_on": "2025-11-21",
        "activity_id": 9,
        "comments": "coding"
    }

    Required: hours + (project_id or issue_id)
    """
    data = parse_input(input)
    hours = data.get("hours")
    project_id = data.get("project_id")
    issue_id = data.get("issue_id")

    if hours is None:
        return "Error: hours is required."
    if not project_id and not issue_id:
        return "Error: project_id or issue_id is required."

    redmine = get_redmine()

    create_kwargs = {
        "hours": hours,
    }
    if project_id:
        create_kwargs["project_id"] = project_id
    if issue_id:
        create_kwargs["issue_id"] = issue_id
    if "spent_on" in data:
        create_kwargs["spent_on"] = data["spent_on"]
    if "activity_id" in data:
        create_kwargs["activity_id"] = data["activity_id"]
    if "comments" in data:
        create_kwargs["comments"] = data["comments"]

    entry = redmine.time_entry.create(**create_kwargs)
    return f"Time entry created: {entry.id}"


@tool("update_time_entry")
@guard_tool("update_time_entry")
def update_time_entry(input: Any = None) -> str:
    """
    Update a time entry.

    Input JSON:
    {
        "time_entry_id": 100,
        "hours": 2.0,
        "spent_on": "2025-11-22",
        "comments": "fixed bug"
    }
    """
    data = parse_input(input)
    te_id = data.get("time_entry_id")
    if not te_id:
        return "Error: time_entry_id is required."

    redmine = get_redmine()
    entry = redmine.time_entry.get(te_id)

    allowed = ["hours", "spent_on", "comments", "activity_id"]
    changes = {k: v for k, v in data.items() if k in allowed}
    if not changes:
        return "No valid fields to update."

    entry.save(**changes)
    return f"Time entry {te_id} updated."


@tool("delete_time_entry")
@guard_tool("delete_time_entry")
def delete_time_entry(input: Any = None) -> str:
    """
    Delete a time entry.

    Input JSON: {"time_entry_id": 100}
    """
    data = parse_input(input)
    te_id = data.get("time_entry_id")
    if not te_id:
        return "Error: time_entry_id is required."

    redmine = get_redmine()
    entry = redmine.time_entry.get(te_id)
    entry.delete()
    return f"Time entry {te_id} deleted."


# ============================================================
# AI analysis tools
# ============================================================

@tool("analyze_project")
@guard_tool("analyze_project")
def analyze_project(input: Any = None) -> str:
    """
    Analyze project issues with AI.

    Input JSON: {"project_id": 1}

    It will fetch issues, build a text summary, and call Azure OpenAI
    via analyze_redmine_issues_with_openai.
    """
    data = parse_input(input)
    pid = data.get("project_id")

    if not pid:
        return "Error: project_id is required."

    redmine = get_redmine()
    issues = redmine.issue.filter(project_id=pid, limit=200)

    if not issues:
        return f"No issues found for project {pid}."

    text = "\n".join([
        f"- {i.id} {i.subject}: {getattr(i, 'description', '')}"
        for i in issues
    ])

    return analyze_redmine_issues_with_openai(text)


# ============================================================
# Tool list for Agent
# ============================================================

TOOLS = [
    # project
    list_projects,
    get_project,
    create_project,

    # issues (read)
    get_project_issues,
    get_issue,
    search_issues,

    # issues (write)
    create_issue,
    update_issue,
    delete_issue,
    set_issue_status,
    assign_issue,
    set_issue_priority,
    set_issue_dates,
    add_note,

    # users
    list_users,
    get_user,
    find_user_by_name,

    # project members
    list_project_members,

    # wiki
    update_wiki,
    get_wiki_page,
    list_wiki_pages,
    delete_wiki_page,

    # time entries
    list_time_entries,
    add_time_entry,
    update_time_entry,
    delete_time_entry,

    # AI
    analyze_project,
]
