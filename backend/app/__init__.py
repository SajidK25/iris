from flask import Flask, jsonify
from flask_cors import CORS

def create_app():
    app = Flask(__name__)

    # Configure CORS to allow requests from your frontend with credentials support
    CORS(
        app,
        origins=["https://iris-sigma-ebon.vercel.app"],
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "Accept"],
        methods=["GET", "POST", "OPTIONS"]
    )

    # Register Blueprint
    print("DEBUG: Registering search_bp")
    app.register_blueprint(search_bp)
    print("DEBUG: search_bp registered successfully")

    @app.route("/api/health", methods=["GET"])
    def health_check():
        print("DEBUG: /api/health endpoint hit")
        return jsonify({"status": "ok", "message": "API is running"})

    @app.errorhandler(404)
    def not_found(error):
        print(f"DEBUG: 404 error for {request.url}")
        return jsonify({"error": "Not found", "message": "The requested resource does not exist"}), 404

    @app.after_request
    def log_response(response):
        print(f"DEBUG: Response Status: {response.status}")
        print(f"DEBUG: Response Headers: {response.headers}")
        return response

    return app