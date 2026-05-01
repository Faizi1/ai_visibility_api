from flask import Flask, jsonify


def register_error_handlers(app: Flask):

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": str(e)}), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "rate_limited", "message": "Too many requests. Slow down."}), 429

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "internal_error", "message": "Something went wrong on our end."}), 500
