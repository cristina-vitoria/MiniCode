def calculate_tax(subtotal_cents: int, rate_percent: int) -> int:
    """Retorna o imposto em centavos, truncando frações de centavo."""
    if type(subtotal_cents) is not int or subtotal_cents < 0:
        raise ValueError("Subtotal deve ser inteiro não negativo.")
    if type(rate_percent) is not int or not 0 <= rate_percent <= 100:
        raise ValueError("Alíquota deve ser um inteiro entre 0 e 100.")
    # TASK 02: há um defeito intencional no cálculo desta regra de negócio.
    return subtotal_cents * rate_percent // 1000
