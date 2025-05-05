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

    @app.route("/api/health", methods=["GET"])
    def health_check():
        """Health check endpoint to verify the API is running"""
        return jsonify({"status": "ok", "message": "API is running"})

    return app