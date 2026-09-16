# Cinema Ticket Pricing & Booking Engine

A FastAPI cinema booking service backed by a real SQLite file. It supports any number of cinemas, screens, shows, seat tiers, individual seats, time-bounded offers, exact Decimal pricing, itemized bills, sellout protection, and concurrent booking safety.

## Prerequisites

- Python 3.11 or newer
- A POSIX shell (commands below use `python3`)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Seed and run

The seed script creates `cinema.db` with 2 cinemas, 3 screens, 3 shows, 3 tiers per show, individual seats, and flat plus capped-percentage offers. The deliberately messy sample price list is at `scripts/sample_messy_prices.csv`.

```bash
python -m scripts.seed
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

The seed is deterministic on a fresh database: show `1` has Silver tier `1`, Gold tier `2`, and Recliner tier `3`. Use the availability endpoint to discover IDs when using an existing database.

## Example requests

```bash
curl http://127.0.0.1:8000/shows/1/availability
curl -X POST http://127.0.0.1:8000/shows/1/quote \
	-H 'content-type: application/json' \
	-d '{"selections":[{"tier_id":1,"quantity":2}],"offer_code":"MEMBER10"}'
curl -X POST http://127.0.0.1:8000/shows/1/book \
	-H 'content-type: application/json' \
	-d '{"selections":[{"tier_id":1,"quantity":2}],"offer_code":"FEST100"}'
curl http://127.0.0.1:8000/bookings/1
```

Import the sample CSV and receive the complete cleaning report. The endpoint accepts a raw `text/csv` request body, and stores the supplied filename with the report.

```bash
curl -X POST 'http://127.0.0.1:8000/price-lists/import?filename=sample_messy_prices.csv' \
	-H 'content-type: text/csv' \
	--data-binary @scripts/sample_messy_prices.csv
curl http://127.0.0.1:8000/price-lists/imports/1
```

The report's `imported` entries are cleaned tier name/price inputs for show creation. Every data row appears in exactly one of `imported`, `deduplicated`, or `rejected`.

Every quote and booking response contains additive `line_items` and `total_payable`. Subtotal rows are informational zero-value rows whose exact amount is included in the description; this avoids double-counting a subtotal while preserving a complete displayed breakdown.

## Tests

```bash
pytest -q
```

The concurrency test creates a real temporary SQLite file, launches 10 simultaneous HTTP booking requests for the same last seat, and verifies exactly one `201`, nine `409` responses, and one booked seat:

```bash
pytest -q tests/test_concurrency.py
```

## Configuration

Settings can be provided through environment variables: `DATABASE_URL`, `CONVENIENCE_FEE_PER_TICKET`, `GST_RATE`, `GST_TAXABLE_BASE` (`fee`, `discounted_subtotal`, or `subtotal_plus_fee`), and `CURRENCY_SYMBOL`.
