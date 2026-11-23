def calculate_discount(subtotal_cents: int, percentage: int) -> int:
    if type(subtotal_cents) is not int or subtotal_cents < 0:
        raise ValueError('subtotal')
    if type(percentage) is not int or not 0 <= percentage <= 100:
        raise ValueError('percentage')
    return subtotal_cents * percentage // 100
