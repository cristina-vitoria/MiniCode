"""Rotas delegam transporte HTTP aos controllers."""
from flask import Blueprint
from .controllers import health, list_products, create_user

api = Blueprint("api", __name__)
api.add_url_rule("/health", view_func=health, methods=["GET"])
api.add_url_rule("/products", view_func=list_products, methods=["GET"])
api.add_url_rule("/users", view_func=create_user, methods=["POST"])
