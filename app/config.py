import os

class BaseConfig:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False

class DevConfig(BaseConfig):
    DEBUG = True
    ENV = 'development'

class ProdConfig(BaseConfig):
    DEBUG = False
    ENV = 'production'
    SESSION_COOKIE_SECURE = True
