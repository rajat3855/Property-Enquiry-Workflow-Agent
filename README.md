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

> This version is a deterministic workflow prototype, not an LLM-powered agent. The matching catalogue is demo data; never treat its availability as live. It does not send messages, book viewings, or make tenancy decisions.

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

## Next steps
1. Add tests for urgency, maintenance routing, missing preferences, and no-match cases.
2. Add an LLM provider behind a service interface for extracting structured fields from free text, with schema validation and deterministic fallback.
3. Add webhook authentication/signature verification and idempotency.
4. Replace demo catalogue with a trusted property/CRM API and verify availability before any booking handoff.
5. Add workflow automation through n8n/Make only after defining retry, failure, and human-escalation behaviour.
