import os
from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

def create_app():
    load_dotenv()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    flask_app = Flask(
        __name__,
        static_folder=os.path.join(project_root, 'static'),
        static_url_path='/static',
        instance_relative_config=True
    )
    os.makedirs(flask_app.instance_path, exist_ok=True)

    flask_app.config['SQLALCHEMY_DATABASE_URI']        = os.getenv('DATABASE_URL')
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    flask_app.config['SECRET_KEY']                     = os.getenv('SECRET_KEY')

    db.init_app(flask_app)
    migrate.init_app(flask_app, db)

    # Ensure models loaded so tables can be created
    from app import models  # noqa
    with flask_app.app_context():
        db.create_all()

    @flask_app.route('/')
    def index():
        return redirect(url_for('estimates.list_estimates'))

    from app.bundles.routes   import bp as bundles_bp
    from app.estimates.routes import bp as estimates_bp

    flask_app.register_blueprint(bundles_bp,   url_prefix='/bundles')
    flask_app.register_blueprint(estimates_bp, url_prefix='/estimates')

    return flask_app
