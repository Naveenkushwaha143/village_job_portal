# village_job_portal

SMS-based skill and labor directory for villages. The project now includes a FastAPI website plus JSON APIs, while keeping the original SMS parsing engine and SQLite worker directory underneath.

## What it does

- Workers can register themselves through an SMS-style message.
- Farmers or households can search using simple phrases like `Need Tractor Mechanic in Rampur`.
- The backend parses the message, maps it to a skill, searches an indexed SQLite directory, and returns the top 3 available contacts.
- Every worker now has a separate profile page with age, phone, skill, rates, photo/logo option, and last 2 months of work history.
- Booking owner, current work status, and progress update (`काम कहाँ तक पहुँचा`) are shown on worker cards/profile/admin dashboard.

## Tech stack

- Python 3.11+
- FastAPI for website and API routes
- Jinja2 templates plus custom CSS for the browser UI
- SQLite for fast local search and simple deployment

## Project layout

- `src/village_job_portal/parser.py`: SMS intent and keyword parsing
- `src/village_job_portal/db.py`: SQLite schema initialization, registration, and search
- `src/village_job_portal/service.py`: Shared business logic for SMS, API, and website flows
- `src/village_job_portal/app.py`: FastAPI app with HTML pages and JSON endpoints
- `src/village_job_portal/templates/index.html`: Main website template
- `src/village_job_portal/templates/worker_profile.html`: Separate worker profile page
- `src/village_job_portal/static/styles.css`: Website styling
- `src/village_job_portal/cli.py`: CLI to initialize the database and simulate incoming SMS traffic
- `tests/test_service.py`: End-to-end unit tests for SMS logic
- `tests/test_web.py`: Route tests for the FastAPI app

## Install dependencies

```bash
cd /workspaces/village_job_portal
python -m pip install -e .
```

## Run the website

Start the FastAPI app:

```bash
cd /workspaces/village_job_portal
python -m uvicorn village_job_portal.app:app --host 0.0.0.0 --port 8000 --reload
```

Then open `http://127.0.0.1:8000` in the browser.

## Google OAuth setup (real login)

Set environment variables before starting the server:

```bash
export GOOGLE_OAUTH_CLIENT_ID="your-google-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-google-client-secret"
```

Callback URL in Google Console should be:

```text
http://127.0.0.1:8000/auth/google/callback
```

## CLI quick start

Create the database with sample worker records:

```bash
PYTHONPATH=src python -m village_job_portal.cli --db-path data/village_jobs.db init-db --seed
```

Simulate a search SMS:

```bash
PYTHONPATH=src python -m village_job_portal.cli --db-path data/village_jobs.db sms \
	--from-phone 9876500000 \
	"Need Tractor Mechanic in Rampur"
```

Simulate a worker registration SMS:

```bash
PYTHONPATH=src python -m village_job_portal.cli --db-path data/village_jobs.db sms \
	--from-phone 9990000001 \
	"REGISTER, Sita Devi, Plumber, Rampur, 9990000001"
```

Run the test suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## API examples

Search through JSON API:

```bash
curl -X POST http://127.0.0.1:8000/api/sms \
	-H "Content-Type: application/json" \
	-d '{"from_phone":"9876500000","message":"Need Tractor Mechanic in Rampur"}'
```

Register a worker through JSON API:

```bash
curl -X POST http://127.0.0.1:8000/api/register \
	-H "Content-Type: application/json" \
	-d '{"name":"Sita Devi","phone":"9990000001","skill":"Plumber","village":"Rampur","age":30,"hourly_rate":180,"daily_rate":1200,"image_url":"https://example.com/photo.jpg"}'
```

## Example flows

Search:

```text
Input: Need Tractor Mechanic in Rampur
Output: Top 3 Tractor Mechanic contacts: 1. Ramesh Yadav - 9000000001 (Rampur, rating 4.8) ...
```

Registration:

```text
Input: REGISTER, Ramesh, Tractor Mechanic, Rampur, 9876543210
Output: Registered Ramesh as Tractor Mechanic in Rampur. Contact saved: 9876543210.
```

## Next production steps

- Connect the API to an SMS gateway such as Twilio, Exotel, or a telecom aggregator.
- Track worker availability windows and last-active timestamps.
- Add pincode, block, and district tags for broader search.
- Add Hindi and regional-language keyword dictionaries for better SMS parsing.