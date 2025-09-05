import os
import logging
from flask import Flask, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

from .config import DevConfig, ProdConfig

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name: str | None = None) -> Flask:
    """Application factory with environment based configuration."""
    load_dotenv()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app = Flask(
        __name__,
        static_folder=os.path.join(project_root, 'static'),
        static_url_path='/static',
        instance_relative_config=True,
    )
    os.makedirs(app.instance_path, exist_ok=True)

    # Pick configuration
    env = config_name or os.getenv('ENV') or os.getenv('FLASK_ENV') or 'production'
    cfg_cls = DevConfig if env == 'development' else ProdConfig
    app.config.from_object(cfg_cls)

    # Initialise logging
    logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO)

    db.init_app(app)
    migrate.init_app(app, db)

    # Ensure models loaded so tables can be created
    from app import models  # noqa
    with app.app_context():
        db.create_all()

    @app.route('/')
    def index():
        return redirect(url_for('estimates.list_estimates'))

    @app.errorhandler(404)
    def not_found(_):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(_):
        return render_template('errors/500.html'), 500

    from app.bundles.routes import bp as bundles_bp
    from app.estimates.routes import bp as estimates_bp
    from app.integrations.repairshopr_export import rs_export_cli

    app.register_blueprint(bundles_bp, url_prefix='/bundles')
    app.register_blueprint(estimates_bp, url_prefix='/estimates')
    app.cli.add_command(rs_export_cli)

    return app
