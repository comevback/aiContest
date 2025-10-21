from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import os
from dotenv import load_dotenv
from redminelib import Redmine
from redminelib.exceptions import AuthError, ResourceNotFoundError

# Load environment variables from .env file
load_dotenv()

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")

if not REDMINE_URL or not REDMINE_API_KEY:
    raise ValueError("REDMINE_URL and REDMINE_API_KEY must be set in the .env file")

try:
    redmine = Redmine(REDMINE_URL, key=REDMINE_API_KEY)
except AuthError:
    raise ValueError("Failed to authenticate with Redmine. Check your API key.")
except Exception as e:
    raise ValueError(f"Failed to connect to Redmine: {e}")

app = FastAPI()

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mock Data (will be replaced by Redmine data where possible)
MOCK_PROGRESS_DATA = {
    1: [ # Project Alpha
        {"week": "Week 1", "planned": 20, "actual": 18, "predicted": 18},
        {"week": "Week 2", "planned": 40, "actual": 35, "predicted": 36},
        {"week": "Week 3", "planned": 60, "actual": 52, "predicted": 58},
        {"week": "Week 4", "planned": 80, "actual": 70, "predicted": 75},
        {"week": "Week 5", "planned": 100, "actual": None, "predicted": 88},
        {"week": "Week 6", "planned": 100, "actual": None, "predicted": 98},
    ],
    2: [ # Project Beta
        {"week": "Week 1", "planned": 15, "actual": 15, "predicted": 15},
        {"week": "Week 2", "planned": 30, "actual": 28, "predicted": 29},
        {"week": "Week 3", "planned": 45, "actual": 40, "predicted": 42},
        {"week": "Week 4", "planned": 60, "actual": None, "predicted": 55},
    ],
    3: [ # Project Gamma
        {"week": "Week 1", "planned": 25, "actual": 22, "predicted": 23},
        {"week": "Week 2", "planned": 50, "actual": 48, "predicted": 49},
        {"week": "Week 3", "planned": 75, "actual": None, "predicted": 70},
    ]
}

class ProjectAnalysisRequest(BaseModel):
    project_id: str

@app.get("/api/projects")
async def get_projects():
    """Returns a list of projects from Redmine."""
    try:
        projects = redmine.project.all(limit=100) # Fetch up to 100 projects
        project_list = []
        for project in projects:
            project_list.append({"id": project.id, "name": project.name, "identifier": project.identifier})
        return {"projects": project_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects from Redmine: {e}")

@app.get("/api/projects/{project_id}/issues")
async def get_issues(project_id: int):
    """Returns issues for a given project ID from Redmine."""
    try:
        issues = redmine.issue.filter(project_id=project_id, limit=100) # Fetch up to 100 issues
        issue_list = []
        for issue in issues:
            issue_data = {
                "id": issue.id,
                "subject": issue.subject,
                "status": {"name": issue.status.name} if hasattr(issue.status, 'name') else None,
                "priority": {"name": issue.priority.name} if hasattr(issue.priority, 'name') else None,
                "assigned_to": {"name": issue.assigned_to.name} if hasattr(issue, 'assigned_to') else None,
                "created_on": str(issue.created_on) if hasattr(issue, 'created_on') else None,
                "updated_on": str(issue.updated_on) if hasattr(issue, 'updated_on') else None,
                "due_date": str(issue.due_date) if hasattr(issue, 'due_date') else None,
            }
            issue_list.append(issue_data)
        return {"issues": issue_list}
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found in Redmine")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch issues from Redmine: {e}")

@app.get("/api/projects/{project_id}/export/{format}")
async def export_data(project_id: int, format: str):
    """Simulates exporting project data in various formats."""
    # In a real application, you would generate the actual file content
    # and return it with appropriate headers.
    time.sleep(1) # Simulate work
    return {"message": f"Exported project {project_id} data in {format} format."}

@app.post("/api/analyze")
async def analyze_project(request_body: ProjectAnalysisRequest):
    """Simulates project analysis."""
    project_id = request_body.project_id

    # Simulate some analysis
    time.sleep(2)
    analysis_result = f"Detailed AI analysis for project {project_id}: This project shows a moderate risk of delay due to several high-priority open issues. Consider reallocating resources to critical path items. Key areas for improvement include better task breakdown and more frequent progress updates."
    return {"analysis": analysis_result}

@app.get("/api/projects/{project_id}/progress-prediction")
async def get_progress_prediction(project_id: int):
    """Returns mock progress prediction data for a given project ID."""
    progress_data = MOCK_PROGRESS_DATA.get(project_id, [])
    if not progress_data:
        raise HTTPException(status_code=404, detail="Progress data not found for this project")
    return {"progress_data": progress_data}
