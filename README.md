# Village Job Portal — SMS-based Skill & Labor Directory

> **"Gaon ke skilled logon ko zyada kaam milega aur jaruratmand ko turant madad."**

A lightweight **offline LinkedIn / JustDial for rural India**.  
Local mistri, mechanic, plumber, and mazdoor register their number once.  
Any farmer or villager can find them instantly by sending a plain SMS.

---

## How It Works

```
Farmer sends SMS:  "Need Tractor Mechanic in Sitapur"
                            │
                     SMS Parsing Engine
                    (keyword extraction)
                            │
                     SQL Database Query
                  (top-3 by rating + location)
                            │
              SMS Reply sent back to farmer:
  ┌─────────────────────────────────────────────────────┐
  │ Village Job Portal                                  │
  │ Aapke liye 2 tractor mechanic mile:                │
  │ ---                                                 │
  │ 1. Ramesh Kumar (Sitapur) - +919876543210 [4.8/5]  │
  │ 2. Suresh Yadav (Hardoi)  - +919876543211 [4.5/5]  │
  └─────────────────────────────────────────────────────┘
```

**Supported SMS formats** (Hindi and English both work):

| What you need | Example SMS |
|---|---|
| Tractor mechanic | `Need Tractor Mechanic` / `Tractor kharab ho gaya` |
| Mason / Mistri | `Mistri chahiye diwaar banwani hai` |
| Plumber | `Plumber bhejo paani ka pipe leak hai` |
| Electrician | `Bijli wala chahiye` |
| Harvesting labour | `Fasal kaatne ke liye mazdoor chahiye` |
| Carpenter | `Carpenter needed urgently` |
| Painter | `Paint karna hai ghar mein` |
| Welder | `Welding kaam chahiye iron grill ke liye` |

Add **`in <village>`** to any message to prefer workers from that area:  
`"Need mason in Sitapur"` → Sitapur workers ranked first.

---

## Project Structure

```
village_job_portal/
├── app/
│   ├── __init__.py
│   ├── database.py       # DB init, seed data, query helpers
│   ├── sms_parser.py     # SMS keyword extraction & skill matching
│   └── sms_handler.py    # Orchestrator: parse → query → format reply
├── db/
│   └── schema.sql        # SQLite schema (workers, skill_aliases, sms_requests)
├── tests/
│   ├── test_database.py
│   ├── test_sms_handler.py
│   └── test_sms_parser.py
├── demo.py               # End-to-end runnable demo
├── requirements.txt
└── README.md
```

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/Naveenkushwaha143/village_job_portal.git
cd village_job_portal

# 2. No third-party packages needed for the core engine.
#    Install pytest only if you want to run the test suite:
pip install pytest

# 3. Run the demo (initialises a fresh DB + simulates 10 SMS requests)
python demo.py
```

---

## Running Tests

```bash
pytest tests/ -v
```

All 55 tests should pass.

---

## Database Schema

### `workers`
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| name | TEXT | Worker's full name |
| phone | TEXT UNIQUE | Mobile number (E.164 format) |
| skill | TEXT | Canonical skill (lowercase) |
| location | TEXT | Village / area |
| is_available | INTEGER | 1 = available, 0 = busy |
| rating | REAL | 1.0–5.0 star rating |

### `skill_aliases`
Maps Hindi/local keyword variants to canonical skill names.  
Example: `"mistri"` → `"mason"`, `"bijli"` → `"electrician"`.

### `sms_requests`
Audit log of every incoming SMS and the reply that was sent.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **SQLite** | Zero-config, runs on any server or Raspberry Pi |
| **No third-party dependencies** | Works offline, no pip install needed in production |
| **Longest-match phrase strategy** | "tractor mechanic" wins over plain "mechanic" |
| **Stop-word removal** | "Need", "chahiye", "bhejo" etc. filtered before matching |
| **Location preference, not filter** | Workers from requested village ranked first, others still shown — guarantees results in thin markets |
| **Top-3 results** | Fits a standard 160-character SMS; configurable via `MAX_RESULTS` |

---

## Production Integration

To hook this up to a real SMS gateway (e.g. Twilio or MSG91):

1. Add `flask` and `twilio` to `requirements.txt`.
2. Expose a webhook endpoint that calls `handle_incoming_sms()`.
3. Use the Twilio SDK to send the returned string as an SMS reply.

```python
# Minimal Flask + Twilio webhook example
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from app.database import init_db
from app.sms_handler import handle_incoming_sms

app = Flask(__name__)
init_db()

@app.route("/sms", methods=["POST"])
def sms_reply():
    body   = request.form.get("Body", "")
    sender = request.form.get("From", "")
    reply  = handle_incoming_sms(sender, body)
    resp   = MessagingResponse()
    resp.message(reply)
    return str(resp)
```

---

## Impact

- **Skilled workers** in villages get more work opportunities via direct calls.  
- **Farmers and households** get instant help without depending on word-of-mouth.  
- Works on **feature phones** — no smartphone or internet required.  
- The audit log in `sms_requests` can be used to understand demand patterns and guide skill-training programs.
