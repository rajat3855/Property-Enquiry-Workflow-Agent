
import json
import os
import sqlite3
import requests

DB_PATH = os.getenv("DB_PATH", "property_workflow.db")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"


# TOOL 1: Search the property database
def search_properties(budget_gbp=None, area=None, bedrooms=None):
    query = """
        SELECT id, title, area, monthly_rent_gbp, bedrooms
        FROM properties
        WHERE available = 1
    """
    params = []

    if budget_gbp is not None:
        query += " AND monthly_rent_gbp <= ?"
        params.append(budget_gbp)

    if bedrooms is not None:
        query += " AND bedrooms = ?"
        params.append(bedrooms)

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(query, params).fetchall()

    properties = [dict(row) for row in rows]

    if area:
        matching_area = [
            prop for prop in properties
            if area.lower() in prop["area"].lower()
        ]

        # If no area match exists, do not pretend
        # that a different area is an exact match.
        properties = matching_area

    return properties[:5]


# TOOL 2: Request a human review
def request_human_review(reason):
    return {
        "action": "human_review",
        "required": True,
        "reason": reason
    }


# Ask the LLM to choose an approved tool
def choose_tool(message, category, priority):
    prompt = f"""
You are a property enquiry workflow agent.

Choose exactly one action:
- search_properties
- request_human_review

Rules:
- Maintenance enquiries must request human review.
- High-priority enquiries must request human review.
- Normal property searches and viewing requests should search properties.

Return only valid JSON in this format:
{{
  "tool": "search_properties or request_human_review",
  "reason": "short explanation"
}}

Customer message: {message}
Detected category: {category}
Detected priority: {priority}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        },
        timeout=120
    )

    response.raise_for_status()
    result = response.json()
    decision = json.loads(result["response"])

    allowed_tools = {
        "search_properties",
        "request_human_review"
    }

    if decision.get("tool") not in allowed_tools:
        raise ValueError("The AI selected an unsupported tool.")

    return decision


# Agent: select a tool, execute it, and return its result
def run_agent(message, category, priority,
              budget_gbp=None, area=None, bedrooms=None):

    # Enforce safety rules independently of the model.
    if priority == "high" or category in (
    "maintenance",
    "general_enquiry"
):
        decision = {
            "tool": "request_human_review",
            "reason": "Urgent or maintenance enquiry"
        }
    else:
        try:
            decision = choose_tool(message, category, priority)
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError
        ):
            # Safe fallback if the model is unavailable
            # or returns invalid output.
            decision = {
                "tool": "search_properties",
                "reason": "Fallback to property search"
            }

    if decision["tool"] == "request_human_review":
        tool_result = request_human_review(
            decision.get("reason", "Human review requested")
        )

    else:
        tool_result = {
            "action": "search_properties",
            "properties": search_properties(
                budget_gbp=budget_gbp,
                area=area,
                bedrooms=bedrooms
            )
        }

    return {
        "selected_tool": decision["tool"],
        "reason": decision.get("reason", ""),
        "tool_result": tool_result
    }



if __name__ == "__main__":
    test_cases = [
        {
            "message": (
                "Find a two-bedroom flat in Park View "
                "under £1200."
            ),
            "category": "viewing_request",
            "priority": "normal",
            "budget_gbp": 1200,
            "area": "Park View",
            "bedrooms": 2
        },
        {
            "message": (
                "Urgent! There is a serious leak "
                "in my apartment. Please help immediately."
            ),
            "category": "maintenance",
            "priority": "high",
            "budget_gbp": None,
            "area": None,
            "bedrooms": None
        }
    ]

    for number, test in enumerate(test_cases, start=1):
        print(f"\n--- Test {number} ---")
        print("Customer:", test["message"])

        result = run_agent(**test)

        print(json.dumps(result, indent=4))
