from flask import jsonify, request, g
from werkzeug.exceptions import HTTPException
from functools import wraps

def install_api_errors(app):
    @app.errorhandler(HTTPException)
    def _http_exception(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": e.name.lower().replace(" ", "_"), "message": e.description}), e.code
        return e

    @app.errorhandler(Exception)
    def _unhandled_exception(e):
        app.logger.exception("Unhandled error")
        if request.path.startswith("/api/"):
            return jsonify({"error": "server_error", "message": "An internal error occurred."}), 500
        return "Internal Server Error", 500

def install_api_auth(login_manager):
    @login_manager.request_loader
    def load_user_from_request(req):
        header = req.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            from app.models.api import authenticate
            from app.models import User
            user_id = authenticate(header[7:].strip())
            if user_id:
                return User.query.get(user_id)
        return None

def require_idempotency(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        from flask_login import current_user
        from app.extensions import db
        from app.models.api import ApiIdempotency
        
        key = (request.headers.get("Idempotency-Key") or "").strip()
        if not key or len(key) > 80:
            return jsonify({"error": "idempotency_key_required", "message": "Supply a UUID in the Idempotency-Key header."}), 400
        
        g.idempotency_key = key
        
        # Check if we already processed this
        existing = ApiIdempotency.query.filter_by(user_id=current_user.id, key=key).first()
        if existing and existing.response_status is not None:
            return jsonify(existing.response_body), existing.response_status
            
        # Create a placeholder row if it doesn't exist (locks out concurrent requests)
        if not existing:
            db.session.add(ApiIdempotency(user_id=current_user.id, key=key))
            db.session.commit() # Commit early to lock the unique constraint
            
        return view(*args, **kwargs)
    return wrapper
