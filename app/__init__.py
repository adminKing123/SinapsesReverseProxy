from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from flask_cors import CORS

from app.config import Config, load_syn_core_config
from app.extensions import db, migrate


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config["SYN_CORE_CONFIG"] = load_syn_core_config()

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    CORS(
        app,
        resources={
            r"/api/syncore/open/*": {
                "origins": "*",
                "methods": ["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"],
                "allow_headers": ["Content-Type", "X-Service-Key", "Authorization"],
            },
            r"/api/syncore/temp/*": {
                "origins": "*",
                "methods": ["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"],
                "allow_headers": ["Content-Type", "X-Service-Key", "Authorization"],
            },
        },
    )

    from app.routes.docs import docs_bp
    from app.routes.health import health_bp
    from app.routes.syncore_open import syncore_open_bp
    from app.routes.temp_user_logs import temp_logs_bp

    app.register_blueprint(docs_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(syncore_open_bp)
    app.register_blueprint(temp_logs_bp)

    if os.environ.get("FLASK_ENV") == "development" or app.debug:
        logging.basicConfig(level=logging.INFO)

    return app