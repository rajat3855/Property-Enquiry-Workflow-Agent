
import json
import re
import requests


def extract_property_details(message):
    prompt = f"""
Extract property details from the customer message.

Return ONLY a valid JSON object with these fields:
{{
    "location": null,
    "bedrooms": null,
    "budget_gbp": null
}}


Rules:
- Extract a location only when the customer explicitly mentions
  a specific place name, such as Park View, Northside,
  Riverside, or City Centre.
- Words such as apartment, flat, house, home, property,
  building, or neighbourhood are not location names by themselves.
- Never guess or invent a location.
- If no specific place name is mentioned, return null.
- If the location is unclear or ambiguous, return null.
- Extract bedrooms as an integer:
  studio = 0, one-bedroom = 1, two-bedroom = 2,
  three-bedroom = 3, and so on.
- If the number of bedrooms is not stated, return null.
- Extract the budget as a numeric amount in GBP.
- Convert expressions such as "£1,200", "1200 pounds",
  or "under £1200" to 1200.
- Do not confuse a bedroom count with a budget.
- If no budget is mentioned, return null.
- Return only facts supported by the customer message.
- Do not include category or priority.
- Return valid JSON only.

Customer message:
{message}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=120
        )

        response.raise_for_status()
        result = response.json()
        extracted = json.loads(result["response"])

        # Validate AI-extracted fields
        location = extracted.get("location")
        if not isinstance(location, str) or not location.strip():
            location = None
        
    # Validate the extracted bedroom count
        bedrooms = extracted.get("bedrooms")

        if (
            not isinstance(bedrooms, int)
            or isinstance(bedrooms, bool)
            or bedrooms < 0
    ):
            bedrooms = None

        
        budget = extracted.get("budget_gbp")

    # Reject invalid budget values
        if (
            not isinstance(budget, (int, float))
            or isinstance(budget, bool)
            or budget < 0
    ):
            budget = None

    # Do not accept a budget if the customer did not mention one
        budget_pattern = (
            r"£\s*\d[\d,]*(?:\.\d+)?"
            r"|\b\d[\d,]*(?:\.\d+)?\s*(?:GBP|pounds?)\b"
    )

        if not re.search(budget_pattern, message, re.IGNORECASE):
            budget = None


        # Determine category with Python rules
        text = message.lower()

        if any(word in text for word in [
            "repair", "broken", "leak", "heating", "maintenance"
        ]):
            category = "maintenance"

        elif any(word in text for word in [
            "viewing", "view", "visit", "appointment"
        ]):
            category = "viewing_request"

        elif any(word in text for word in [
            "rent", "available", "property", "flat",
            "apartment", "bedroom"
        ]):
            category = "property_enquiry"

        else:
            category = "general_enquiry"

        # Determine priority independently of the AI
        urgent_pattern = (
            r"\burgent\b|\bemergency\b|\basap\b|"
            r"\bimmediately\b|\bright away\b"
        )

        priority = (
            "high"
            if re.search(urgent_pattern, text)
            else "normal"
        )

        return {
            "category": category,
            "location": location,
            "bedrooms": bedrooms,
            "budget_gbp": budget,
            "priority": priority
        }

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to Ollama. Check that it is running."
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Ollama timed out. Please try again."
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(f"Ollama request failed: {error}")

    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError(f"Invalid AI response: {error}")


if __name__ == "__main__":
    test_messages = [
        "I need a two-bedroom flat near Park View for up to £1200 per month.",
        "Urgent! There is a leak in my apartment. Please fix it immediately.",
        "Can I arrange a viewing for a one-bedroom flat?"
    ]

    for message in test_messages:
        print("\nCustomer:", message)

        try:
            print(json.dumps(
                extract_property_details(message),
                indent=4
            ))
        except RuntimeError as error:
            print("Error:", error)
