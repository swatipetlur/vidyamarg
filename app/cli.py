"""Command line helpers:  flask --app run init-db | create-admin | seed"""
import click
from werkzeug.security import generate_password_hash

from . import db
from .models import user as user_model


def init_app(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables (safe to run repeatedly)."""
        db.init_db()
        click.echo("Database ready.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt="Full name")
    @click.option("--email", prompt="Email")
    @click.password_option("--password", prompt="Password (min 8 characters)")
    def create_admin_command(name, email, password):
        """Create an administrator account (admins cannot self-register)."""
        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters.")
        if user_model.get_by_email(email):
            raise click.ClickException("A user with that email already exists.")
        user_model.create_user(name.strip(), email, generate_password_hash(password), "admin")
        click.echo(f"Administrator {email} created.")

    @app.cli.command("seed")
    def seed_command():
        """Load clearly-labelled SAMPLE examinations, rules and notes."""
        from .seed import seed_sample_data

        created = seed_sample_data()
        click.echo("Sample data loaded." if created else "Data already present; nothing changed.")
