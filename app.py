"""
app.py — Application Entry Point
----------------------------------
Creates the Flask app, registers blueprints, sets up teardown hooks,
initialises the database, and starts the development server.

Run:
    python app.py
"""
import os
from flask import Flask
import config
from models.db import close_db, init_db
from routes.auth     import auth
from routes.customer import customer
from routes.admin    import admin


def create_app() -> Flask:
    """Flask application factory."""
    app = Flask(__name__)

    # ── Configuration ─────────────────────────────────────────────────────────
    app.secret_key          = config.SECRET_KEY
    app.config["UPLOAD_FOLDER"]        = config.UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"]   = config.MAX_CONTENT_LENGTH
    
    # Mail Config
    app.config['MAIL_SERVER'] = config.MAIL_SERVER
    app.config['MAIL_PORT'] = config.MAIL_PORT
    app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
    app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
    app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD
    app.config['MAIL_DEFAULT_SENDER'] = config.MAIL_DEFAULT_SENDER

    # Initialize Mail
    from services.mail_service import mail
    mail.init_app(app)

    # ── Register Blueprints ───────────────────────────────────────────────────
    app.register_blueprint(auth)
    app.register_blueprint(customer)
    app.register_blueprint(admin)

    # ── Database Teardown ─────────────────────────────────────────────────────
    app.teardown_appcontext(close_db)

    # ── Initialize DB (creates tables + seeds admin) ──────────────────────────
    with app.app_context():
        init_db(app)

    return app


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    application = create_app()
    print("=" * 55)
    print("  AI Food Quality Analysis System — Phase 1")
    print("  Running at http://127.0.0.1:5000")
    print(f"  Admin: {config.ADMIN_EMAIL} / {config.ADMIN_PASS}")
    print("=" * 55)
    application.run(debug=True, host="0.0.0.0", port=5000)
