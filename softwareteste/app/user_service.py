def register_user(store, payload):
    """TASK 05: falta validação de campos antes de persistir o usuário."""
    return store.add_user(
        name=payload.get("name"),
        email=payload.get("email"),
        age=payload.get("age"),
    )
