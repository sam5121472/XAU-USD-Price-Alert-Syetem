# Samzy XAU/USD Assistant

Gold-price dashboard with real alerting — no LLM in the loop. The
dashboard talks straight to an MCP server, which is the only thing that
touches Excel, the price API, and email

```
web_app.py  ─▶  MCP Server (mcp_server.py)
                        │
        ┌───────────────┼───────────────┐
        ▼                ▼                ▼
  price_client.py   excel_store.py   email_client.py
        │                ▼                │
   goldprice.dev     alerts.xlsx      Resend API
                          ▲
                          │
                    Alert Worker (separate always-on process,
                    polls goldprice.dev, checks alerts.xlsx,
                    fires email_client.py when a target hits)
```

The code is split into two packages that mirror this, joined only at
`app/mcp_server.py`:

```
app/
  alert_system/       -- owns alerts.xlsx, the price API, the email
    excel_store.py       client, and the background worker
    price_client.py
    email_client.py
    alert_worker.py
  mcp_server.py       -- exposes alert_system's capabilities as MCP tools
  web_app.py          -- plain REST dashboard backend that calls those
                          tools directly (no LLM, no chat)
```

- **`app/mcp_server.py`** — the MCP server. Exposes 4 tools: `get_price`,
  `create_price_alert`, `list_price_alerts`, `delete_price_alert`,
  implemented by calling into `app/alert_system/`.
- **`app/web_app.py`** — the dashboard backend (FastAPI + a small HTML/JS
  front end). On startup it launches `mcp_server.py` as a child process and
  holds an MCP client session open to it for the app's lifetime. Its
  endpoints (`GET /api/price`, `GET /api/alerts`, `POST /api/alerts`,
  `DELETE /api/alerts/{id}`) each call exactly one MCP tool — there's no
  natural-language layer, so the UI is a form and a list, not a chat box.
- **`app/alert_system/alert_worker.py`** — a separate, always-on process.
  Polls goldprice.dev on a timer, checks every *active* row in
  `alerts.xlsx`, and emails you via Resend the moment a target is hit, then
  marks it triggered. It never talks to the MCP server or web app — it just
  reads/writes the same spreadsheet directly.

The web app and the worker are independent processes that both read/write
`alerts.xlsx` (via `app/alert_system/excel_store.py`), coordinated with a
file lock — you run both.

## 1. Install

```bash
cd samzy
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure

Your API keys are already filled into `.env`. Check it over:

- `GOLDPRICE_API_KEY` — from goldprice.dev. Free tier = 1,000 calls/month.
- `RESEND_API_KEY` — from Resend.
- `RESEND_FROM_EMAIL` — must be `onboarding@resend.dev` (only delivers to
  your own Resend account email) **or** an address on a domain you've
  verified in your Resend dashboard. Swap this in before relying on alerts.
- `ALERT_TO_EMAIL` — set this to your email so the dashboard form can leave
  the email field blank and still work.
- `POLL_INTERVAL_MINUTES` — default 60, tuned to stay inside goldprice.dev's
  free-tier monthly quota. Lower it only if you're on a paid plan (see the
  comment in `.env` for the math).

**Security note:** these keys were pasted into our chat at an earlier point,
so treat them as lightly exposed — consider rotating them once everything's
confirmed working. Never commit `.env` (already in `.gitignore`).

## 3. Run it (two terminals)

**Terminal 1 — the alert worker** (checks price, sends emails):
```bash
python -m app.alert_system.alert_worker
```

**Terminal 2 — the dashboard:**
```bash
uvicorn app.web_app:app --reload
```
Open **http://localhost:8000**. Fill in the form to create an alert; the
list below it shows active/triggered alerts with a delete button on each.

## Notes & things you may want to change.

- **Excel as the datastore**: fine for personal, single-machine use. The
  file lock keeps the worker and web app from corrupting each other's
  writes, but this isn't built for concurrent multi-user access — if you
  outgrow that, swap `app/alert_system/excel_store.py` for SQLite and
  nothing else needs to change, since both the MCP server and the worker
  only import from that one file.
- **Using this MCP server elsewhere**: since it's a real stdio MCP server,
  you can also point Claude Desktop (or any other MCP client) at
  `python -m app.mcp_server` directly — that's the natural way back in if
  you ever want a natural-language front end again, without touching
  `app/alert_system/` at all.
- **Rate limits**: `/api/price` (the ticker in the UI) is cached for 60s
  server-side so refreshing the page a lot won't burn your goldprice.dev
  quota. The worker's own polling interval is the main quota consumer —
  see the `.env` comment.
- **A quirk worth knowing if you edit `web_app.py`**: this MCP SDK version
  returns one content block *per list item* for tools that return a list
  (so an empty list is 0 blocks, a 1-item list is 1 block, etc.) rather than
  one block containing a JSON array. `_tool_blocks_to_list()` in
  `web_app.py` handles this — if you add new endpoints, parse results
  through it rather than assuming a single JSON blob.
