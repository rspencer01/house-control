from flask import Blueprint

bp = Blueprint("robots", __name__)


@bp.route("/robots.txt")
def robots():
    return send_from_directory(application.static_folder, request.path[1:])
