def process_invoice(invoice):
    """Process an invoice."""
    total = 0
    for line in invoice.lines:
        if line.price > 100:
            total = total + line.price * 0.9
        else:
            total = total + line.price
    if invoice.discount:
        total = total * 0.95
    return round(total, 2)
