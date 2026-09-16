from decimal import Decimal

from ticket_pricing import BookingRequest, SeatClass, SeatSelection, TicketPricingEngine


prices = {
    "Silver": SeatClass("Silver", Decimal("250.00"), available=20),
    "Gold": SeatClass("Gold", Decimal("350.00"), available=10),
}
request = BookingRequest(
    selections=(SeatSelection("Silver", 2), SeatSelection("Gold", 1)),
    member=True,
    festival_discount=Decimal("50.00"),
)
result = TicketPricingEngine(prices).price(request)
for item in result.line_items:
    print(f"{item.description}: ₹{item.amount:.2f}")
print(f"Grand Total: ₹{result.total:.2f}")
