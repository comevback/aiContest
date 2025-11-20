from redminelib import Redmine
from redminelib.exceptions import AuthError
from fastapi import HTTPException

def get_redmine_instance(redmine_url: str, redmine_api_key: str):
    if not redmine_url or not redmine_api_key:
        raise HTTPException(
            status_code=400, detail="Redmine URL and API Key are required."
        )
    try:
        redmine = Redmine(redmine_url, key=redmine_api_key)
        redmine.auth()
        return redmine
    except AuthError:
        raise HTTPException(
            status_code=401, detail="Failed to authenticate with Redmine."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to Redmine: {e}"
        )
