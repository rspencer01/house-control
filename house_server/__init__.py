from flask import (
    Flask,
    redirect,
    url_for,
    session,
    request,
    render_template,
    send_from_directory,
    redirect,
    jsonify,
    flash,
    abort,
)
from urllib2 import Request, urlopen, URLError
import json
import yaml
import time
import os
from datetime import datetime

from logging.config import dictConfig
from Model import *


def create_application(test_config=None):
    configuration = yaml.load(open("config.yaml", "r"))
    if test_config is not None:
        configuration.update(test_config)

    dictConfig(configuration["logging"])

    application = Flask(__name__)
    application.debug = True
    application.secret_key = "laekdfjlkajsfpwiejr1oj3204-1044"
    application.config["SQLALCHEMY_DATABASE_URI"] = configuration["database"]
    application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(application)

    from . import robots
    from . import auth

    auth = auth.create_blueprint(test_config)

    application.register_blueprint(robots.bp)
    application.register_blueprint(auth)

    @application.template_filter("strftime")
    def _jinja2_filter_datetime(date, fmt=None):
        native = datetime.fromtimestamp(date)
        format = "%X %d/%m/%Y"
        return native.strftime(format)

    @application.route("/")
    @auth.login_required
    def index():
        return render_template(
            "index.html",
            data=open("/tmp/data").read(),
            lights=Light.query.all(),
            last_modified=os.path.getmtime("/tmp/data"),
        )

    @application.route("/edit/light/<light_id>", methods=["GET", "POST"])
    @auth.login_required
    def edit_light(light_id):
        light = Light.query.filter_by(id=light_id).first()
        if light is None:
            return redirect(url_for("index"))

        if request.method == "GET":
            return render_template("edit_light.html", light=light)

        if request.method == "POST":
            light.name = request.form["name"]
            db.session.commit()
            flash('Updated light "%s"' % light.name, "success")
            return redirect(url_for("index"))

    @application.route("/state", methods=["POST"])
    @application.route("/api/state", methods=["POST"])
    @auth.pi_auth_required
    def state():
        data = request.get_json()
        if type(data) is not dict:
            abort(400)
        if "lights" not in data:
            abort(400)
        data = data["lights"]
        if type(data) != list:
            abort(400)
        for entry in data:
            if "id" not in entry or "state" not in entry:
                abort(400)
            light_id = entry["id"]
            light_state = entry["state"]
            if type(light_id) is not unicode:
                abort(400)
            humandecode = {"0": False, "1": True, "Off": False, "On": True}
            if light_state not in humandecode:
                abort(400)
            light_state = humandecode[light_state]
            light = Light.query.get(light_id)

            if light is None:
                light = Light(id=light_id, name=light_id)

            if light.lightstates == [] or light.latest_state().state != light_state:
                light.lightstates.append(
                    LightState(time=int(time.time()), state=light_state)
                )

            db.session.add(light)
            db.session.commit()
        open("/tmp/data", "w").write(str(request.get_json()))
        return "Good job!"

    @application.route("/all", methods=["POST"])
    def all_change():
        if request.form["state"] == "on":
            new_state = True
        elif request.form["state"] == "off":
            new_state = False
        else:
            abort(400)
        for light in Light.query.all():
            light.lightstaterequests.append(
                LightStateRequest(time=int(time.time()), state=new_state, seen=False)
            )
        db.session.commit()

        flash('Switched all lights "%s"' % request.form["state"], "success")
        flash(
            "Currently switching lights is not immediate.  The light will be toggled in real life within a minute, and the below table will reflect the change within a minute after that.",
            "warning",
        )
        return "OK"

    @application.route("/updates", methods=["POST", "GET"])
    def get_updates():
        if request.method == "GET":
            lights_updates = []
            for update in db.session().query(LightStateRequest).filter(
                LightStateRequest.seen == False
            ):
                lights_updates.append(
                    {"id": update.light_id, "state": "on" if update.state else "off"}
                )
                update.seen = True
            db.session.commit()
            return jsonify({"lights": lights_updates})

        elif request.method == "POST":
            light_id = request.form["light_id"]
            new_state = request.form["state"]
            humandecode = {"0": False, "1": True, "off": False, "on": True}
            new_state = humandecode[new_state]
            light = Light.query.get(light_id)
            if not light:
                abort(400)
            light.lightstaterequests.append(
                LightStateRequest(time=int(time.time()), state=new_state, seen=False)
            )
            db.session.commit()
            flash('Toggled light "%s"' % light.name, "success")
            flash(
                "Currently toggling lights is not immediate.  The light will be toggled in real life within a minute, and the below table will reflect the change within a minute after that.",
                "warning",
            )
            return "OK"

    return application


if __name__ == "__main__":
    application = create_application()
    application.run(host="0.0.0.0")
