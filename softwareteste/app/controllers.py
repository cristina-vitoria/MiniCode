from flask import current_app, jsonify, request
from .user_service import register_user


def health():
    return jsonify(status="ok")


def list_products():
    # TASK 03: os parâmetros de paginação ainda não são tratados.
    products = current_app.extensions["store"].list_products()
    return jsonify(items=products, total=len(products))


def create_user():
    payload = request.get_json()
    if not isinstance(payload, dict):
        return jsonify(error="O corpo deve ser um objeto JSON."), 400
    user = register_user(current_app.extensions["store"], payload)
    return jsonify(user), 201
