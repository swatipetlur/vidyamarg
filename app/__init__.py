from pathlib import Path

from flask import Flask, render_template

from config import DEFAULT_SECRET, INSTANCE_DIR, Config


def create_app(config_object=None):
    app = Flask(__name__, instance_path=str(INSTANCE_DIR))
    app.config.from_object(config_object or Config)

    if app.config["ENV_NAME"] == "production" and app.config["SECRET_KEY"] == DEFAULT_SECRET:
        raise RuntimeError("Set a strong SECRET_KEY before running in production.")

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    from . import cli, db, security, templating

    db.init_app(app)
    security.init_app(app)
    templating.init_app(app)
    cli.init_app(app)

    from .auth.routes import bp as auth_bp
    from .routes.admin import bp as admin_bp
    from .routes.bookmarks import bp as bookmarks_bp
    from .routes.exams import bp as exams_bp
    from .routes.main import bp as main_bp
    from .routes.notes import bp as notes_bp
    from .routes.payments import bp as payments_bp

    for blueprint in (main_bp, auth_bp, exams_bp, bookmarks_bp, notes_bp, payments_bp, admin_bp):
        app.register_blueprint(blueprint)

    _register_error_handlers(app)
    return app


def _register_error_handlers(app):
    messages = {
        400: ("Request not accepted", "Something in that request was not valid."),
        403: ("Access denied", "You do not have permission to open this page."),
        404: ("Page not found", "We could not find what you were looking for."),
        413: ("File too large", "That upload is larger than the 16 MB limit."),
        429: ("Too many attempts", "Please wait a few minutes and try again."),
        500: ("Something went wrong", "An unexpected error occurred. Please try again."),
    }

    def handler(error):
        code = getattr(error, "code", 500) or 500
        title, default = messages.get(code, messages[500])
        detail = getattr(error, "description", None)
        if not detail or detail == getattr(type(error), "description", None):
            detail = default
        return render_template("errors/error.html", code=code, title=title, detail=detail), code

    for code in messages:
        app.register_error_handler(code, handler)
