from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    price_cents: int

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class User:
    # Tipos anotados não validam entradas em tempo de execução.
    id: int
    name: str
    email: str
    age: int

    def to_dict(self):
        return asdict(self)
