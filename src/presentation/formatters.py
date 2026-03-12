"""Formatadores de dados para a camada de apresentação."""

from decimal import Decimal


def format_currency(value) -> str:
    """Formata um valor em moeda brasileira."""
    if isinstance(value, Decimal):
        value = float(value)
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

