from fastapi import APIRouter, HTTPException, Header
from typing import List, Dict, Any

from backend.redmine.client import get_redmine_instance
from backend.redmine.issues import (
    get_issues_logic,
    export_data_logic,
    get_project_progress_prediction_logic,
    get_issue_progress_prediction_logic,
)
from backend.redmine.wiki import WikiPageUpdateRequest, upsert_wiki_page
from backend.redmine.analysis import ProjectAnalysisRequest, analyze_project_logic

router = APIRouter()


@router.get("/projects")
async def get_projects(
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key"),
):
    redmine = get_redmine_instance(x_redmine_url, x_redmine_api_key)
    try:
        projects = redmine.project.all(limit=100)
        return {
            "projects": [
                {"id": p.id, "name": p.name, "identifier": p.identifier}
                for p in projects
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch projects from Redmine: {e}"
        )


@router.get("/projects/{project_id}/issues")
async def get_issues(
    project_id: int,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key"),
):
    """Returns issues for a given project ID from Redmine."""
    issue_list = await get_issues_logic(project_id, x_redmine_url, x_redmine_api_key)
    return {"issues": issue_list}


@router.get("/projects/{project_id}/export/{format}")
async def export_data(
    project_id: int,
    format: str,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key"),
):
    """Exports project data in various formats."""
    return await export_data_logic(project_id, format, x_redmine_url, x_redmine_api_key)


@router.post("/analyze")
async def analyze_project(
    request_body: ProjectAnalysisRequest,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key"),
):
    """Analyzes project issues using Azure OpenAI."""
    return await analyze_project_logic(
        request_body.project_id, x_redmine_url, x_redmine_api_key
    )


@router.post("/projects/{project_identifier}/wiki")
async def update_wiki(
    project_identifier: str,
    request_body: WikiPageUpdateRequest,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key"),
):
    """Updates a Redmine wiki page with the given content."""
    try:
        result = upsert_wiki_page(
            base_url=x_redmine_url,
            project_identifier=project_identifier,
            title=request_body.title,
            text=request_body.content,
            api_key=x_redmine_api_key,
            comment=request_body.comment,
        )
        if result.get("ok"):
            return {"message": "Wiki page updated successfully.", "details": result}
        else:
            raise HTTPException(
                status_code=result.get("status", 500),
                detail=result.get("body", "Failed to update wiki page."),
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while updating wiki: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@router.get("/projects/{project_id}/progress-prediction")
async def get_project_progress_prediction(
    project_id: int,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key"),
):
    """Returns overall project progress prediction data."""
    return await get_project_progress_prediction_logic(
        project_id, x_redmine_url, x_redmine_api_key
    )


@router.get("/issues/{issue_id}/progress-prediction")
async def get_issue_progress_prediction(
    issue_id: int,
    x_redmine_url: str = Header(..., alias="X-Redmine-Url"),
    x_redmine_api_key: str = Header(..., alias="X-Redmine-Api-Key"),
):
    """Returns progress prediction data for a single issue."""
    return await get_issue_progress_prediction_logic(
        issue_id, x_redmine_url, x_redmine_api_key
    )
