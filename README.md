# Property Enquiry Workflow Agent

A small backend prototype for a property/lettings workflow. It accepts enquiries through a REST API, categorises and prioritises them, searches a demo property catalogue using structured preferences, records the enquiry in SQLite, and flags cases that should be reviewed by a person.

## Why this project
It models a practical workflow relevant to AI automation: capture structured data, apply transparent rules, connect the enquiry to property records, and route uncertain or sensitive cases to a human rather than pretending every request can be automated.

## Features
- FastAPI REST endpoints with JSON request/response schemas
- SQLite persistence for enquiries and property listings
- Enquiry categorisation and urgency detection
- Budget, area, and bedroom-based property matching
- Human-review routing for urgent, maintenance, and general/ambiguous cases
- Health check and bounded enquiry-history endpoint
- Seeded demo properties for repeatable local testing

>

## Run locally
```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```
Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## Example request
```json
{
  "name": "Asha",
  "email": "asha@example.com",
  "message": "I would like to arrange a viewing for a two bedroom flat",
  "budget_gbp": 1200,
  "preferred_area": "Park View",
  "bedrooms": 2,
  "source": "website_form"
}
```

## Endpoints
- `GET /health` — service health
- `POST /enquiries` — classify, match, save, and route an enquiry
- `GET /enquiries?limit=50` — recent enquiry history
- `GET /properties?available_only=true` — catalogue
- `POST /properties` — add a listing

