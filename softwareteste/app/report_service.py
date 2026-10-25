"""TASK 06: comportamento correto com dívida técnica intencional.

Entrada: lista de pedidos com status, channel e items. Cada item tem
price_cents (int >= 0) e quantity (int >= 0). Canais reconhecidos: retail
ou wholesale. Somente pedidos paid desses canais entram no relatório.
Não é necessário validar entradas fora desse contrato nesta tarefa.
"""


def build_sales_report(orders):
    a = 0
    b = 0
    c = 0
    d = 0
    e = 0
    for x in orders:
        if x["status"] == "paid":
            if x["channel"] == "retail":
                y = 0
                z = 0
                for w in x["items"]:
                    if w["quantity"] > 0:
                        y = y + w["price_cents"] * w["quantity"]
                        z = z + w["quantity"]
                a = a + y
                b = b + z
                c = c + 1
                d = d + y
            else:
                if x["channel"] == "wholesale":
                    y = 0
                    z = 0
                    for w in x["items"]:
                        if w["quantity"] > 0:
                            y = y + w["price_cents"] * w["quantity"]
                            z = z + w["quantity"]
                    a = a + y
                    b = b + z
                    c = c + 1
                    e = e + y
    return {"revenue_cents": a, "units": b, "orders": c,
            "by_channel": {"retail": d, "wholesale": e}}
