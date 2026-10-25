def register_user(store, payload):
    name, email, age = payload.get('name'), payload.get('email'), payload.get('age')
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
        raise ValueError('name')
    if not isinstance(email, str):
        raise ValueError('email')
    email = email.strip()
    if email.count('@') != 1 or any(character.isspace() for character in email):
        raise ValueError('email')
    if not all(email.split('@')):
        raise ValueError('email')
    if type(age) is not int or not 0 <= age <= 130:
        raise ValueError('age')
    return store.add_user(name.strip(), email, age)
