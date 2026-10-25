def item_totals(items):
    revenue, units = 0, 0
    for item in items:
        if item['quantity'] > 0:
            revenue += item['price_cents'] * item['quantity']
            units += item['quantity']
    return revenue, units


def build_sales_report(orders):
    result = {'revenue_cents':0,'units':0,'orders':0,'by_channel':{'retail':0,'wholesale':0}}
    for order in orders:
        if order['status'] != 'paid' or order['channel'] not in result['by_channel']:
            continue
        revenue, units = item_totals(order['items'])
        result['revenue_cents'] += revenue
        result['units'] += units
        result['orders'] += 1
        result['by_channel'][order['channel']] += revenue
    return result
