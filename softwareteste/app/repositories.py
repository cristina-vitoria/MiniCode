"""Armazenamento em memória, reiniciado a cada instância da aplicação."""
from .models import Product, User


class Store:
    def __init__(self):
        self.products = [Product(i, f"Produto {i:02d}", i * 1000) for i in range(1, 13)]
        self.users = []
        self.next_user_id = 1

    def list_products(self):
        return [product.to_dict() for product in self.products]

    def add_user(self, name, email, age):
        user = User(self.next_user_id, name, email, age)
        self.users.append(user)
        self.next_user_id += 1
        return user.to_dict()
