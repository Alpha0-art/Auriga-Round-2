# Design Reasoning

## Domain model

Cinema, Screen, and Show are separate because a venue can have multiple screens and each screen can host many scheduled shows. SeatTier belongs to a show because prices and inventory can differ by show. Seat is an individual row, rather than a counter, so the system can claim concrete seats and prove that no seat was booked twice. Offers are independent, time-bounded records. Booking and BookingLineItem preserve the charged bill exactly as it was committed.

## Offers

The engine allows exactly one offer per booking. A request carrying one offer whose database record is marked `stackable` is rejected by the pure engine; this intentionally prevents ambiguous combinations and keeps quote and booking calculations identical. Flat offers subtract their value, capped percentage offers subtract `min(subtotal * percentage / 100, cap)`, and discounts never make the subtotal negative.

## GST and rounding

The default taxable base is the convenience fee only. `GST_TAXABLE_BASE` can select `fee`, `discounted_subtotal`, or `subtotal_plus_fee`, so the policy is configuration rather than hidden business logic. All money is Decimal and is quantized with `ROUND_HALF_UP` to two places after every multiplication, addition, discount, fee, and tax calculation.

Bill component rows are additive. The displayed Subtotal and Discounted Subtotal rows are informational zero-value rows with their calculated values in the description; otherwise including both component lines and summary lines would double-count. The randomized pricing test asserts that the sum of every returned amount equals the final total exactly.

## Concurrency and sellout safety

SQLite connections disable its implicit transaction mode and use an explicit `BEGIN IMMEDIATE` for every SQLAlchemy transaction. A booking request therefore obtains SQLite's reserved write lock before it checks availability. It selects available Seat rows inside that transaction, verifies the requested count, changes those exact rows to `BOOKED`, inserts the booking and line items, and commits as one unit. Other writers wait on SQLite's configured busy timeout, then see the committed seat state and receive HTTP 409. The ten-thread test exercises this behavior against one remaining seat.

## Limitations and production additions

The service has no authentication or authorization, payment gateway, refund/cancellation workflow, seat-hold expiry worker, audit log, or multi-currency support. A larger production deployment would normally use PostgreSQL row locks (`SELECT ... FOR UPDATE`), connection pooling and migrations, authenticated operators/customers, payment idempotency keys, refund accounting, observability, and a dedicated seat-hold lifecycle.
