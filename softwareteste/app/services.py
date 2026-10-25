"""Regras completas. TASK 04: ainda não existe tests/test_services.py.

As funções aceitam somente os tipos e faixas documentados e não fazem I/O.
"""


def shipping_cost(subtotal_cents: int) -> int:
    """Frete de 1500 centavos abaixo de 20000; a partir de 20000 é grátis.

    ValueError para subtotal negativo ou de tipo diferente de int (inclui bool).
    """
    if type(subtotal_cents) is not int or subtotal_cents < 0:
        raise ValueError("Subtotal inválido.")
    return 0 if subtotal_cents >= 20000 else 1500


def loyalty_points(subtotal_cents: int) -> int:
    """Um ponto por 1000 centavos completos; mesma validação de shipping_cost."""
    if type(subtotal_cents) is not int or subtotal_cents < 0:
        raise ValueError("Subtotal inválido.")
    return subtotal_cents // 1000


def normalize_coupon(code: str) -> str:
    """Remove espaços nas pontas e converte para maiúsculas.

    Após normalizar, aceita apenas 3 a 12 caracteres ASCII em A-Z e 0-9.
    ValueError para tipo diferente de str ou conteúdo fora desse contrato.
    """
    if not isinstance(code, str):
        raise ValueError("Cupom deve ser texto.")
    normalized = code.strip().upper()
    if not 3 <= len(normalized) <= 12 or not normalized.isascii() or not normalized.isalnum():
        raise ValueError("Cupom inválido.")
    return normalized
