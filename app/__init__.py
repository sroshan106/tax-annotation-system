from flask import Flask

def create_app() -> Flask:
    app = Flask(__name__)
    from app.security import init_security
    init_security(app)
    from app.routes import bp
    app.register_blueprint(bp)
    return app
