from flask import Flask, jsonify
from flask_classful import FlaskView, route
from flask_cors import CORS
from request_logic import handle_info, handle_cam_status, handle_timelapse_list, handle_timelapse_latest, handle_reset_stream
from scheduler import start_scheduler
from logging_setup import setup_logger
from settings import FLASK_HOST, FLASK_PORT, FLASK_DEBUG

logger = setup_logger("plant_server")


class PlantAPI(FlaskView):
    route_base = "/"
    @route("/info", methods=["GET"])
    def info(self):
        return jsonify(handle_info())
    @route("/cam/status", methods=["GET"])
    def cam_status(self):
        return jsonify(handle_cam_status())
    @route("/timelapse", methods=["GET"])
    def timelapse_list(self):
        return jsonify(handle_timelapse_list())
    @route("/timelapse/latest", methods=["GET"])
    def timelapse_latest(self):
        result = handle_timelapse_latest()
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result)
    @route("/cam/reset/<int:cam_id>", methods=["POST"])
    def reset_stream(self, cam_id):
        return jsonify(handle_reset_stream(cam_id))


def create_app():
    app = Flask(__name__)
    CORS(app)
    PlantAPI.register(app)
    return app


def run():
    app = create_app()
    start_scheduler()
    logger.info(f"Plant backend starting on {FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)


if __name__ == "__main__":
    run()
