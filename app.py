
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import os
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ai_extractor import extract_property_details
from agent_tools import run_agent


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv(
    "DB_PATH",
    str(BASE_DIR / "property_workflow.db")
)

app = FastAPI(
    title="Property Enquiry Workflow Agent",
    version="2.0.0"
)


# --------------------------------------------------
# FRONTEND
# --------------------------------------------------

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "index.html")


# --------------------------------------------------
# DATA MODELS
# --------------------------------------------------

class Enquiry(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: Optional[str] = None
    message: str = Field(min_length=3, max_length=3000)
    budget_gbp: Optional[float] = Field(default=None, ge=0)
    preferred_area: Optional[str] = None
    bedrooms: Optional[int] = Field(default=None, ge=0, le=20)
    source: str = "api"


class Property(BaseModel):
    title: str
    area: str
    monthly_rent_gbp: float = Field(gt=0)
    bedrooms: int = Field(ge=0)
    available: bool = True


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as con:

        con.execute("""
            CREATE TABLE IF NOT EXISTS enquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                message TEXT NOT NULL,
                budget_gbp REAL,
                preferred_area TEXT,
                bedrooms INTEGER,
                source TEXT,
                category TEXT,
                priority TEXT,
                status TEXT,
                summary_json TEXT,
                created_at TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                area TEXT NOT NULL,
                monthly_rent_gbp REAL NOT NULL,
                bedrooms INTEGER NOT NULL,
                available INTEGER NOT NULL DEFAULT 1
            )
        """)

        count = con.execute(
            "SELECT COUNT(*) FROM properties"
        ).fetchone()[0]

        if count == 0:
            con.executemany(
                """
                INSERT INTO properties(
                    title,
                    area,
                    monthly_rent_gbp,
                    bedrooms,
                    available
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("City Centre One-Bed Flat",
                     "City Centre", 950, 1, 1),

                    ("Riverside Two-Bed Apartment",
                     "Riverside", 1250, 2, 1),

                    ("Northside Studio",
                     "Northside", 725, 0, 1),

                    ("Park View Two-Bed Flat",
                     "Park View", 1100, 2, 1),
                ]
            )


init_db()


# --------------------------------------------------
# BASIC CLASSIFICATION
# --------------------------------------------------

def classify(message: str):
    text = message.lower()

    urgent_terms = (
        "urgent",
        "today",
        "asap",
        "emergency",
        "immediately"
    )

    viewing_terms = (
        "viewing",
        "view",
        "visit",
        "appointment"
    )

    maintenance_terms = (
        "repair",
        "broken",
        "leak",
        "heating",
        "maintenance"
    )

    if any(term in text for term in maintenance_terms):
        category = "maintenance"

    elif any(term in text for term in viewing_terms):
        category = "viewing_request"

    elif any(term in text for term in (
        "rent",
        "available",
        "property",
        "flat",
        "apartment",
        "bedroom"
    )):
        category = "property_enquiry"

    else:
        category = "general_enquiry"

    priority = (
        "high"
        if any(term in text for term in urgent_terms)
        else "normal"
    )

    return category, priority


# --------------------------------------------------
# PROPERTY MATCHING
# Retained for compatibility with the existing project
# --------------------------------------------------

def find_matches(budget, area, bedrooms):
    sql = """
        SELECT id, title, area, monthly_rent_gbp, bedrooms
        FROM properties
        WHERE available = 1
    """

    params = []

    if budget is not None:
        sql += " AND monthly_rent_gbp <= ?"
        params.append(budget)

    if bedrooms is not None:
        sql += " AND bedrooms = ?"
        params.append(bedrooms)

    with connect() as con:
        rows = con.execute(sql, params).fetchall()

    results = [dict(row) for row in rows]

    if area:
        exact = [
            prop for prop in results
            if area.lower() in prop["area"].lower()
        ]

        if exact:
            results = exact

    return results[:5]


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "property-enquiry-workflow-agent"
    }


# --------------------------------------------------
# ADD A PROPERTY
# --------------------------------------------------

@app.post("/properties")
def add_property(prop: Property):
    with connect() as con:
        cur = con.execute(
            """
            INSERT INTO properties(
                title,
                area,
                monthly_rent_gbp,
                bedrooms,
                available
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                prop.title,
                prop.area,
                prop.monthly_rent_gbp,
                prop.bedrooms,
                int(prop.available)
            )
        )

        return {
            "property_id": cur.lastrowid,
            "created": True
        }


# --------------------------------------------------
# LIST PROPERTIES
# --------------------------------------------------

@app.get("/properties")
def list_properties(available_only: bool = True):
    query = "SELECT * FROM properties"

    if available_only:
        query += " WHERE available = 1"

    with connect() as con:
        rows = con.execute(query).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------
# CREATE ENQUIRY + AI AGENT
# --------------------------------------------------

@app.post("/enquiries")
def create_enquiry(enquiry: Enquiry):

    # STEP 1: Extract information using the LLM
    try:
        ai_details = extract_property_details(
            enquiry.message
        )

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"AI extraction failed: {error}"
        ) from error

    # STEP 2: Read AI-extracted details
    category = ai_details.get(
        "category",
        "general_enquiry"
    )

    priority = ai_details.get(
        "priority",
        "normal"
    )

    # STEP 3: Combine AI results with form values
    preferred_area = (
        ai_details.get("location")
        or enquiry.preferred_area
    )

    bedrooms = (
        ai_details.get("bedrooms")
        if ai_details.get("bedrooms") is not None
        else enquiry.bedrooms
    )

    budget_gbp = (
        ai_details.get("budget_gbp")
        if ai_details.get("budget_gbp") is not None
        else enquiry.budget_gbp
    )

    # STEP 4: Run the tool-using AI agent
    try:
        agent_result = run_agent(
            message=enquiry.message,
            category=category,
            priority=priority,
            budget_gbp=budget_gbp,
            area=preferred_area,
            bedrooms=bedrooms
        )

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Agent execution failed: {error}"
        ) from error

    # STEP 5: Read the selected tool's result
    selected_tool = agent_result["selected_tool"]
    tool_result = agent_result["tool_result"]

    if selected_tool == "search_properties":
        matches = tool_result.get("properties", [])
    else:
        matches = []

    # STEP 6: Decide whether human review is needed
    needs_human = (
        priority == "high"
        or category in (
            "maintenance",
            "general_enquiry"
        )
        or selected_tool == "request_human_review"
    )

    # STEP 7: Determine enquiry status
    if needs_human:
        status = "human_review"

    elif matches:
        status = "matched"

    else:
        status = "needs_follow_up"

    # STEP 8: Prepare the result for the frontend
    summary = {
        "category": category,
        "priority": priority,
        "budget_gbp": budget_gbp,
        "preferred_area": preferred_area,
        "bedrooms": bedrooms,
        "matching_properties": matches,
        "human_review_required": needs_human,
        "selected_tool": selected_tool,
        "agent_reason": agent_result.get("reason", ""),
        "note": (
            "Matches are suggestions from demo data. "
            "Verify current availability before offering "
            "a viewing."
        )
    }

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    # STEP 9: Save the enquiry in SQLite
    with connect() as con:
        cur = con.execute(
            """
            INSERT INTO enquiries(
                name,
                email,
                message,
                budget_gbp,
                preferred_area,
                bedrooms,
                source,
                category,
                priority,
                status,
                summary_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                enquiry.name,
                enquiry.email,
                enquiry.message,
                budget_gbp,
                preferred_area,
                bedrooms,
                enquiry.source,
                category,
                priority,
                status,
                json.dumps(summary),
                created_at
            )
        )

        enquiry_id = cur.lastrowid

    # STEP 10: Return the result to the frontend
    return {
        "enquiry_id": enquiry_id,
        "category": category,
        "priority": priority,
        "status": status,
        "summary": summary,
        "created_at": created_at
    }


# --------------------------------------------------
# LIST ENQUIRIES
# --------------------------------------------------

@app.get("/enquiries")
def list_enquiries(limit: int = 50):

    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 200"
        )

    with connect() as con:
        rows = con.execute(
            """
            SELECT
                id,
                name,
                email,
                message,
                category,
                priority,
                status,
                created_at
            FROM enquiries
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    return [dict(row) for row in rows]
