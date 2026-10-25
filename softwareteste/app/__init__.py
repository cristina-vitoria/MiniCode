from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .config import Config
from .repositories import Store
from .routes import api


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    app.json.sort_keys = app.config["JSON_SORT_KEYS"]
    app.extensions["store"] = Store()
    app.register_blueprint(api)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    return app
