# AI_LOGS

## User request

Build a complete, real, production-grade Cinema Ticket Pricing & Booking Engine. This must be a fully working system end-to-end — no demo, no prototype, no mock data, no dummy logic. It must generalize to any cinema and any show, not be hardcoded to one example scenario.

CONTEXT:
A multiplex booking counter keeps mis-pricing tickets. Seats come in tiers (e.g. Silver, Gold, Recliner) at different prices per show. Tiers must sell out correctly and become unbookable once full. There are two offers: a flat festival discount, and a percentage discount for members with a maximum cap. Every booking adds a per-ticket convenience fee and GST on top. The final total must be exact to the paisa, and every bill must show a full line-by-line breakup, not just a total. Get the plain booking total right first, then layer on the offers, the fee, and the tax, in that order.

TECH STACK:
Python 3.11+, FastAPI, SQLAlchemy, SQLite (real file-based persistence, not in-memory), Pydantic for schemas, Decimal for all currency math (never floats), pytest for testing.

DATA MODEL (real database tables):
- Cinema (id, name)
- Screen (id, cinema_id, name)
- Show (id, screen_id, movie_name, start_time)
- SeatTier (id, show_id, name, base_price, total_seats) — support any number of tiers
- Seat (id, tier_id, seat_number, status: AVAILABLE/HELD/BOOKED)
- Offer (id, code, type: FLAT or PERCENT_CAPPED, value, cap nullable, active_from, active_to, stackable boolean)
- Booking (id, show_id, offer_code_used, created_at, total_amount)
- BookingLineItem (id, booking_id, description, amount)

PRICING PIPELINE (build as a pure, independently testable module, pricing_engine.py, with no DB/HTTP dependencies):
1. Plain total = sum of (tier base_price × quantity) across selected tiers
2. Apply offers: FLAT subtracts a fixed amount; PERCENT_CAPPED subtracts min(subtotal × percentage, cap). Pick ONE explicit stacking rule (offers stack, or only one offer allowed per booking) and enforce it in code — document the choice.
3. Add convenience fee = per-ticket fee × total ticket count
4. Add GST using a configurable taxable base (decide exactly what GST applies to — e.g. the fee only, or the full discounted subtotal — and make it a config value, not a hardcoded assumption)
5. Final total. Use Decimal with ROUND_HALF_UP at 2 decimal places at every step. Write a fuzz test with at least 20 randomized cases proving the sum of all returned line items equals the final total exactly, to the paisa.

SELLOUT ENFORCEMENT:
Track individual Seat rows, not just counters, so a specific seat can never be double-booked. Booking a tier with insufficient available seats must return HTTP 409 with a clear error message, enforced inside a database transaction that checks and locks seat availability atomically before committing.

CONCURRENCY SAFETY (required, not optional):
Configure SQLite transactions properly (explicit isolation_level or BEGIN IMMEDIATE), or support Postgres with SELECT ... FOR UPDATE. Write a real concurrency test using threading or asyncio that fires 10 simultaneous booking requests against a show with exactly 1 seat left in a tier, and asserts exactly 1 succeeds and 9 fail cleanly with 409 — no overselling, no double-booked seats, no crashes.

API ENDPOINTS (FastAPI with Pydantic models and correct status codes):
- POST /shows/{show_id}/quote — seat tier + quantity selections plus optional offer code, returns full itemized breakup without committing anything
- POST /shows/{show_id}/book — same input, actually creates the booking, decrements seat inventory, persists line items, returns the booking with its itemized bill
- GET /bookings/{booking_id} — returns the exact stored itemized bill as originally charged
- GET /shows/{show_id}/availability — returns remaining seats per tier
- Return 400/404/409 with clear JSON errors for invalid tier, invalid offer code, quantity ≤ 0, or sold-out tier

REQUIRED BILL FORMAT (every quote/booking response must look like this):
{
	"line_items": [
		{"description": "Silver x2 @ ₹250", "amount": "500.00"},
		{"description": "Gold x1 @ ₹400", "amount": "400.00"},
		{"description": "Subtotal", "amount": "900.00"},
		{"description": "Festival Discount (flat)", "amount": "-100.00"},
		{"description": "Member Discount (10%, capped ₹150)", "amount": "-80.00"},
		{"description": "Discounted Subtotal", "amount": "720.00"},
		{"description": "Convenience Fee (3 x ₹20)", "amount": "60.00"},
		{"description": "GST (18% on fee)", "amount": "10.80"}
	],
	"total_payable": "790.80"
}

SEED SCRIPT:
scripts/seed.py must create at least 2 cinemas, multiple screens/shows, 3+ seat tiers per show with realistic prices, and both offer types, so the API is testable immediately with zero manual database editing.

TESTS (pytest, must actually pass):
- Plain total calculation
- Flat discount
- Percentage discount with cap enforcement
- Offer stacking rule, both allowed and disallowed cases per your chosen rule
- Fee + GST stacking
- Rounding fuzz test (line items sum exactly to total)
- Sellout rejection (409 on full tier)
- Concurrency race condition on last-seat booking
- API integration tests using FastAPI's TestClient against a real temporary SQLite database

REPO STRUCTURE (this must be the ROOT of the repository):
/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── pricing_engine.py
│   ├── database.py
│   └── config.py
├── scripts/
│   └── seed.py
├── tests/
│   ├── test_pricing_engine.py
│   ├── test_api.py
│   └── test_concurrency.py
├── requirements.txt
├── README.md
├── REASONING.md
├── AI_LOGS.md
└── .gitignore

README.md must include: what the project does, prerequisites, exact setup commands (venv, pip install), how to seed the database, how to run the server, how to run tests, example curl requests using real sample IDs from the seed data, and how to verify the concurrency test passes.

REASONING.md must include: the domain model reasoning, the exact offer stacking rule chosen and why, the exact GST base rule chosen and why, the rounding strategy and why it guarantees exact totals, how concurrency and sellout safety were actually achieved with a real explanation of the locking mechanism, and known limitations / what a production version would add (auth, payments, refunds, multi-currency).

AI_LOGS.md must contain the complete, unedited conversation with the AI tool used to build this, pasted exactly as-is with no modification whatsoever — any alteration is a submission violation.

SUBMISSION REQUIREMENT:
The final solution must be pushed to a public GitHub repository. README.md, REASONING.md, and AI_LOGS.md must all sit directly in the repository's root folder (not nested in a subfolder) — this is a hard evaluation requirement.

HARD CONSTRAINTS — do not violate:
- No floats for money anywhere
- No hardcoded single-scenario data in logic, only in seed/config
- No skipped concurrency handling
- No total-only responses; line items are mandatory everywhere a bill appears
- Every claim in REASONING.md must be true of the actual code

Now design the schema, the pricing/discount/tax module, the booking service with concurrency safety, the API layer, and the full test suite, and implement all of it completely and correctly.

## Latest feature log

The expanded backend-only specification added messy CSV seat-class import. The implementation added `app/price_import.py`, `scripts/sample_messy_prices.csv`, the `ImportReport` table, `POST /price-lists/import`, `GET /price-lists/imports/{report_id}`, mutually exclusive report buckets, importer tests, API persistence tests, and documentation of the first-valid-occurrence duplicate rule. The raw `text/csv` endpoint has no frontend/UI dependency. The expanded suite passes 15 tests.

## Assistant work log

The assistant inspected the repository and found only the initial README. It created the requirements file, SQLAlchemy models, file-backed SQLite database setup, Pydantic schemas, Decimal pricing engine, FastAPI application, seed script, and pytest suites. SQLite is configured with `isolation_level = None`, foreign keys, a busy timeout, and an explicit `BEGIN IMMEDIATE` on each transaction. The selected offer policy is exactly one offer per booking, and the default GST base is the convenience fee.

The first pricing check exposed an arithmetic expectation error in the check itself; the engine was corrected to keep subtotal summary rows informational and additive line items exact. The pure pricing suite then passed 6 tests. The API smoke test passed after seeding the same temporary database as the app. The API and concurrency suites passed 3 tests, including exactly one success and nine 409 responses for ten concurrent requests against one seat. Documentation was added with setup, seed, run, curl, test, configuration, reasoning, and limitation details.
