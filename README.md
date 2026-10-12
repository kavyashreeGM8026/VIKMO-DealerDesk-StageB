# VIKMO DealerDesk — AI/ML track

DealerDesk is a Django REST Framework backend for a South Indian automobile spare-parts distributor. It uses PostgreSQL (SQLite is not supported), database-backed catalogue/inventory/order tools, and a Gemini-powered Dealer Assistant. Forecasting and reorder endpoints are a separate remaining AI/ML stage unless present in the current source.

## Requirements

- Python 3.11+
- PostgreSQL
- Packages in `requirements.txt`
- A Google Gemini API key for live assistant requests

## Local setup (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: set DATABASE_URL, DJANGO_SECRET_KEY, and GEMINI_API_KEY
python manage.py migrate
python manage.py seed_data
python manage.py seed_data
python manage.py runserver
```

The app reads real secrets from `.env` for local development. Never commit `.env`; commit `.env.example` with placeholders only.

## Dealer Assistant (Section 9)

`POST /api/assistant/chat/`

Request example:

```json
{
  "session_id": "demo-session",
  "dealer_id": 7,
  "message": "Do you have brake pads for a Pulsar 150?"
}
```

The response follows the API contract: `reply`, `cited_skus`, `tool_calls`, and `actions`. The assistant uses database-backed `search_parts`, `check_stock`, and `create_draft_order` tools. Draft orders use the same server-side serializer and order service as `POST /api/orders/`; the assistant cannot confirm orders. Prices and stock are read from the database at request time.

### Gemini configuration

- Provider: Google Gemini API via the `google-genai` Python SDK.
- Default model: `gemini-3.8-flash` (stable model listed in Google's official Gemini model documentation; availability still depends on your API key/project).
- `GEMINI_API_KEY`: your private key from Google AI Studio.
- `GEMINI_MODEL`: optional model override.
- `GEMINI_TIMEOUT_MS`: request timeout in milliseconds; defaults to `45000`.

Verify model access with your own key before relying on live requests. Do not paste your key into source code, tests, or chat logs.

### Conversation memory limitations

Conversation context is held in a bounded in-process memory cache, keyed by `(dealer_id, session_id)`. Different dealer/session pairs are isolated. Memory is not durable: it is lost on process restart and is not shared between multiple server worker processes. For this assignment's simple runserver use, this avoids adding a new database schema. A production deployment should use shared persistent session storage.

### Run tests without a live Gemini key

The assistant integration tests mock the model call; automated tests should not call Google APIs:

```powershell
python manage.py test core.test_assistant_tools core.test_assistant_chat
python manage.py check
python smoke_test.py --track aiml
```

The smoke test requires the application to be running against a configured PostgreSQL database. Run the full existing suite before submission:

```powershell
python manage.py test
```

### Manual live test

1. Put your real key in the private `.env` as `GEMINI_API_KEY=...`.
2. Confirm `GEMINI_MODEL=gemini-3.8-flash` is available for your API key, or set a supported model.
3. Start the server and use an existing seeded dealer ID:

```powershell
$body = @{ session_id = "manual-demo-1"; dealer_id = 1; message = "Find brake pads for a Pulsar 150 and tell me the current stock and price." } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/assistant/chat/" -ContentType "application/json" -Body $body
```

Do not use an order-creation request for the first live test. Inspect the returned tool calls, cited SKUs, prices, and stock against the database.

## Other APIs and contract

`API_CONTRACT.md` is the authoritative source for endpoint paths, fields, status codes, and the forecasting/reorder formula. Keep the files in `data/` unchanged. The grader installs dependencies on Linux, runs migrations and `seed_data` twice, and then starts Django.
