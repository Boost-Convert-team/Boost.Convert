import click
from flask import Flask

from Blueprints.auth.authentication import normalize_email
from Blueprints.services.access.access_service import PLANS
from extensions import db
from models import Usuario


def register_cli(app: Flask) -> None:
    @app.cli.command("set-plan")
    @click.argument("email")
    @click.argument("plan", type=click.Choice(PLANS))
    def set_plan(email: str, plan: str) -> None:
        """Move an account to the Free or PRO plan.

        Example: flask --app app:create_app set-plan ana@example.com pro
        """
        user = Usuario.query.filter_by(email=normalize_email(email)).first()
        if user is None:
            raise click.ClickException(f"Nenhuma conta com o e-mail {email}.")
        user.plano = plan
        db.session.commit()
        click.echo(f"{user.email} agora esta no plano {plan}.")
