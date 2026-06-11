from typing import Any, Dict, List
import json
import logging
import os
import google.auth
from google import genai
from mcp.server.fastmcp import FastMCP
from google.genai import types
import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

load_dotenv()
port = int(os.environ.get("PORT", 8080))
mcp = FastMCP("gradr", host="0.0.0.0", port=port)

# Initialize client
_, project_id = google.auth.default()
if project_id and not os.environ.get("GOOGLE_CLOUD_PROJECT"):
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
if not os.environ.get("GOOGLE_CLOUD_LOCATION"):
    os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

client = genai.Client(vertexai=True)

def json_string(data: Dict[str, Any]) -> str:
    """Utility: Always return JSON string."""
    return json.dumps(data, ensure_ascii=False, indent=2)


class RubricItem(BaseModel):
    label: str = Field(description="Name or category of the rubric criterion (e.g. accuracy, clarity, completeness)")
    points: int = Field(description="Points allocated for this criterion")


class Rubric(BaseModel):
    rubric_items: List[RubricItem]
    max_score: int = Field(description="The maximum score possible for the question")

@mcp.tool()
def parse_questions(text: str) -> str:
    """
    Parses raw question text into a structured list.

    Args:
        text: Raw question text to parse.

    Returns:
        JSON string with parsed questions.
    """
    try:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        questions = []
        for idx, line in enumerate(lines):
            questions.append({
                "question_id": f"q{idx+1}",
                "text": line
            })

        return json_string({
            "ok": True,
            "questions": questions,
            "count": len(questions)
        })
    except Exception as e:
        return json_string({
            "ok": False,
            "error": f"Failed to parse questions: {str(e)}",
            "tool": "parse_questions"
        })


@mcp.tool()
def parse_marking_guide(text: str, max_score: int) -> str:
    """
    Converts raw marking guide text into a structured rubric using Gemini.

    Args:
        text: Raw marking guide or rubric text.
        max_score: The explicit maximum score attainable from the database.

    Returns:
        JSON string matching {"rubric": {"rubric_items": [...], "max_score": X}}
    """
    try:
        prompt = f"""
        You are an expert curriculum designer.
        Analyze the raw marking guide text below and extract a structured rubric.
        Enforce points allocation for each rubric criterion so that the sum of points of all rubric criteria is exactly {max_score}.
        The total max_score of the rubric itself must be set to {max_score}.

        Raw marking guide:
        {text}
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Rubric,
            )
        )

        rubric_data = json.loads(response.text)
        return json_string({
            "ok": True,
            "rubric": rubric_data
        })
    except Exception as e:
        logger.error(f"parse_marking_guide failed: {e}")
        return json_string({
            "ok": False,
            "error": f"Failed to parse rubric structure: {str(e)}",
            "tool": "parse_marking_guide"
        })


@mcp.tool()
def normalize_answers(text: str) -> str:
    """
    Normalizes student answers (lowercasing, removing noise).

    Args:
        text: Raw student answer text.

    Returns:
        JSON string with normalized text.
    """
    try:
        cleaned = text.strip().lower()
        return json_string({
            "ok": True,
            "normalized": cleaned
        })
    except Exception as e:
        return json_string({
            "ok": False,
            "error": f"Failed to normalize answers: {str(e)}",
            "tool": "normalize_answers"
        })


@mcp.tool()
def trigger_aloc_cache(subject: str, exam_type: str) -> str:
    """
    Triggers the GradrAI Node.js backend to seed and cache past questions from ALOC API.
    Includes a 5-second timeout and 2-retry resilience pattern.

    Args:
        subject: The subject to cache (e.g. chemistry, english)
        exam_type: The exam type (e.g. waec, WAEC)

    Returns:
        Confirmation message or structured error JSON
    """
    backend_url = os.environ.get("GRADR_BACKEND_URL", "http://localhost:5000")
    admin_token = os.environ.get("ADMIN_JWT_TOKEN")

    url = f"{backend_url}/api/practice/admin/cache/trigger"

    headers = {}
    if admin_token:
        headers["Authorization"] = f"Bearer {admin_token}"

    max_retries = 2
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = httpx.post(
                url,
                json={"subject": subject, "examType": exam_type},
                headers=headers,
                timeout=5.0
            )
            if response.status_code == 200:
                return json_string({
                    "ok": True,
                    "message": f"Successfully triggered ALOC cache job for {subject} ({exam_type})",
                    "backend_response": response.json()
                })
            else:
                last_error = f"Backend returned status code {response.status_code}: {response.text}"
        except httpx.TimeoutException:
            last_error = f"Request timed out (attempt {attempt}/{max_retries})"
            logger.warning(f"trigger_aloc_cache timeout attempt {attempt}/{max_retries}")
        except Exception as e:
            last_error = f"HTTP request failed: {str(e)}"
            logger.warning(f"trigger_aloc_cache error attempt {attempt}/{max_retries}: {e}")

    return json_string({
        "ok": False,
        "error": f"ALOC cache trigger failed after {max_retries} attempts: {last_error}",
        "tool": "trigger_aloc_cache"
    })


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
