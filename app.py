import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, Response, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
)

from models import (
    db,
)

from blueprints.users import users_bp
from blueprints.podcasts import podcasts_bp
from blueprints.episodes import episodes_bp

def create_app(testing=False):
    app = Flask(__name__)
    load_dotenv(dotenv_path=".env")

    if testing:
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("POSTGRES_TEST_URL")
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("POSTGRES_URL")
    db.init_app(app)
    app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    CORS(
        app,
        origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            os.getenv("FRONTEND_URL"),
        ],
        supports_credentials=True,
    )
    JWTManager(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(users_bp)
    app.register_blueprint(podcasts_bp)
    app.register_blueprint(episodes_bp)

    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            res = Response()
            res.headers["X-Content-Type-Options"] = "*"
            return res

    @app.after_request
    def refresh_expiring_jwts(response):
        try:
            exp_timestamp = get_jwt()["exp"]
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=30))
            if target_timestamp > exp_timestamp:
                access_token = create_access_token(identity=get_jwt_identity())
                set_access_cookies(response, access_token)
            return response
        except (RuntimeError, KeyError):
            return response

    @app.route("/")
    def hello_world():  # put application's code here
        return "Hello World!"

    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
else:
    app = create_app()
