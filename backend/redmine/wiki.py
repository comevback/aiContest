from fastapi import HTTPException
from pydantic import BaseModel
import requests
import json
from urllib.parse import quote

class WikiPageUpdateRequest(BaseModel):
    title: str
    content: str
    comment: str = ""

def upsert_wiki_page(
    base_url: str,
    project_identifier: str,
    title: str,
    text: str,
    api_key: str,
    comment: str = "",
):
    """
    Creates or updates a wiki page in Redmine.
    """
    url = f"{base_url}/projects/{project_identifier}/wiki/{quote(title)}.json"
    headers = {
        "X-Redmine-API-Key": api_key,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    payload = {"wiki_page": {"text": text, "comments": comment}}

    try:
        # Use PUT to create or update the wiki page
        r = requests.put(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
        )
        r.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # After successful update, get the page details to confirm
        g = requests.get(url, headers=headers)
        g.raise_for_status()

        if g.headers.get("Content-Type", "").startswith("application/json"):
            page = g.json().get("wiki_page", {})
            return {
                "ok": True,
                "title": page.get("title", title),
                "version": page.get("version"),
                "browser_url": f"{base_url}/projects/{project_identifier}/wiki/{quote(title)}",
            }
        else:
            # This case should ideally not be reached if the PUT was successful
            return {"ok": False, "status": g.status_code, "body": g.text}

    except requests.exceptions.RequestException as e:
        print(
            f"ERROR: Failed to upsert wiki page '{title}' for project '{project_identifier}': {e}"
        )
        # Try to provide a more specific error message based on the response
        if e.response is not None:
            status_code = e.response.status_code
            if status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{project_identifier}' or wiki page not found. Ensure the project identifier is correct.",
                )
            elif status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="Redmine authentication failed. Check your API key.",
                )
            elif status_code == 403:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to edit the wiki on this project.",
                )
            else:
                raise HTTPException(
                    status_code=status_code,
                    detail=f"Redmine API error: {e.response.text}",
                )
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to connect to Redmine: {e}"
            )