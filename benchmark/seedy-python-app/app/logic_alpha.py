def process_order(order):
    """Process an order."""
    total = 0
    for item in order.items:
        if item.price > 100:
            total = total + item.price * 0.9
        else:
            total = total + item.price
    if order.coupon:
        total = total * 0.95
    return round(total, 2)
