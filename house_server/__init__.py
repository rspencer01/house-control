from urllib2 import Request, urlopen, URLError
import json
import time
import os
from logging.config import dictConfig
from datetime import datetime

import yaml
from flask import (
    Flask,
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

import house_server.utils
from house_server.Model import *

HUMANDECODE = {
    "off": False, "on": True, "0": False, "1": True, "Off": False, "On": True
}


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
    application.config["SQLALCHEMY_ECHO"] = configuration[
        "SQLALCHEMY_ECHO"
    ] if "SQLALCHEMY_ECHO" in configuration else False

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

    @application.template_filter("counton")
    def _jinja2_filter_counton(lights):
        return len([light for light in lights if light.latest_state().state])

    @application.route("/")
    @auth.login_required
    def index():
        return render_template(
            "index.html",
            groups=LightGroup.query.all(),
            lights=Light.query.all(),
            schedules=Schedule.query.all(),
            last_modified=os.path.getmtime("/tmp/data"),
        )

    @application.route("/lights")
    @auth.login_required
    def lights():
        return render_template(
            "lights.html", groups=LightGroup.query.all(), lights=Light.query.all()
        )

    @application.route("/edit/light/<light_id>", methods=["GET", "POST"])
    @auth.login_required
    def edit_light(light_id):
        light = Light.query.filter_by(id=light_id).first()
        if light is None:
            flash("The requested light could not be found.", "error")
            return redirect(url_for("index"))

        if request.method == "GET":
            return render_template(
                "edit_light.html", light=light, groups=LightGroup.query.all()
            )

        if request.method == "POST":
            if request.form["group"] == "None":
                light.group = None
            else:
                light.group = LightGroup.query.filter_by(
                    id=request.form["group"]
                ).first()
            light.name = request.form["name"]
            db.session.commit()
            flash('Updated light "%s"' % light.name, "success")
            return redirect(url_for("index"))

    @application.route("/state", methods=["POST"])
    @application.route("/api/state", methods=["POST"])
    @auth.pi_auth_required
    def state():
        data = request.get_json()
        if not house_server.utils.check_json_object_format(
            {"lights": [{"id": None, "state": None}]}, data
        ):
            abort(400)
        data = data["lights"]
        for entry in data:
            light_id = entry["id"]
            light_state = entry["state"]
            if type(light_id) is not unicode:
                abort(400)
            if light_state not in HUMANDECODE:
                abort(400)
            light_state = HUMANDECODE[light_state]
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
    def allchange():
        if request.form["state"] not in HUMANDECODE:
            abort(400)
        new_state = HUMANDECODE[request.form["state"]]

        for light in Light.query.all():
            if new_state:
                light.turn_on()
            else:
                light.turn_off()
        db.session.commit()

        flash('Switched all lights "%s"' % request.form["state"], "success")
        flash(
            "Currently switching lights is not immediate.  The light will be toggled in real life within a minute, and the below table will reflect the change within a minute after that.",
            "warning",
        )
        return "OK"

    @application.route("/updates", methods=["POST", "GET"])
    @application.route("/lights/updates", methods=["POST", "GET"])
    def commands():
        if request.method == "GET":
            lights_updates = []
            messages = []
            for update in db.session().query(LightStateRequest).filter(
                LightStateRequest.seen == False
            ):
                lights_updates.append(
                    {"id": update.light_id, "state": "on" if update.state else "off"}
                )
                update.seen = True
            for message in db.session().query(CustomMessage).filter(
                CustomMessage.seen == False
            ):
                messages.append(message.message)
                message.seen = True
            db.session.commit()
            return jsonify({"lights": lights_updates, "messages": messages})

        elif request.method == "POST":
            light_id = request.form["light_id"]
            new_state = request.form["state"]
            new_state = HUMANDECODE[new_state]
            light = Light.query.get(light_id)
            if not light:
                abort(400)
            if new_state:
                light.turn_on()
            else:
                light.turn_off()
            db.session.commit()
            flash('Toggled light "%s"' % light.name, "success")
            flash(
                "Currently toggling lights is not immediate.  The light will be toggled in real life within a minute, and the below table will reflect the change within a minute after that.",
                "warning",
            )
            return "OK"

    @application.route("/messages", methods=["POST"])
    def messages():
        message = request.form["message"]
        db.session.add(
            CustomMessage(time=int(time.time()), message=message, seen=False)
        )
        db.session.commit()
        flash('Sent command "%s"' % message, "success")
        flash("Currently commands are not immediate.", "warning")
        return "OK"

    @application.route("/new_schedule", methods=["POST"])
    @auth.login_required
    def new_schedule():
        schedule = Schedule(name="New", enabled=False)
        db.session.add(schedule)
        db.session.commit()
        flash("Created new schedule", "success")
        return str(schedule.id)

    @application.route("/new_group", methods=["POST"])
    @auth.login_required
    def new_group():
        group = LightGroup(name="New Group")
        db.session.add(group)
        db.session.commit()
        flash("Created new light group", "success")
        return redirect(url_for("manage_groups"))

    @application.route("/delete_group/<group_id>", methods=["POST"])
    @auth.login_required
    def delete_group(group_id):
        group = LightGroup.query.filter_by(id=group_id).first()
        db.session.delete(group)
        db.session.commit()
        flash("Deleted light group", "success")
        return redirect(url_for("manage_groups"))

    @application.route("/manage_groups")
    @auth.login_required
    def manage_groups():
        return render_template("edit_groups.html", groups=LightGroup.query.all())

    @application.route("/edit_group/<group_id>", methods=["GET", "POST"])
    @auth.login_required
    def edit_group(group_id):
        group = LightGroup.query.filter_by(id=group_id).first()
        if request.method == "POST":
            group.name = request.form["name"]
            db.session.commit()
            flash('Updated group "%s"' % group.name, "success")
            return redirect(url_for("manage_groups"))

        else:
            return render_template("edit_group.html", group=group)

    @application.route("/delete_schedule/<schedule_id>", methods=["POST"])
    @auth.login_required
    def delete_schedule(schedule_id):
        schedule = Schedule.query.filter_by(id=schedule_id).first()
        db.session.delete(schedule)
        db.session.commit()
        return redirect(url_for("index"))

    @application.route("/delete_rule/<rule_id>", methods=["POST"])
    @auth.login_required
    def delete_rule(rule_id):
        rule = ScheduleRule.query.filter_by(id=rule_id).first()
        db.session.delete(rule)
        db.session.commit()
        return "OK"

    @application.route("/edit/schedule/<schedule_id>", methods=["GET", "POST"])
    @auth.login_required
    def edit_schedule(schedule_id):
        schedule = Schedule.query.filter_by(id=schedule_id).first()
        if schedule is None:
            flash("The requested schedule could not be found.", "error")
            return redirect(url_for("index"))

        if request.method == "GET":
            return render_template(
                "edit_schedule.html", schedule=schedule, lights=Light.query.all()
            )

        if request.method == "POST":
            schedule.name = request.form["name"]
            schedule.enabled = HUMANDECODE[request.form["enabled"]]
            db.session.commit()
            flash('Updated schedule "%s"' % schedule.name, "success")
            return redirect(url_for("index"))

    @application.route("/add/rule/to/schedule/<schedule_id>", methods=["POST"])
    @auth.login_required
    def add_rule(schedule_id):
        schedule = Schedule.query.filter_by(id=schedule_id).first()
        if schedule is None:
            flash("The requested schedule could not be found.", "error")
            return redirect(url_for("index"))

        light = Light.query.filter_by(id=request.form["light"]).first()
        if schedule is None:
            flash("The requested light could not be found.", "error")
            return redirect(url_for("index"))

        time = int(request.form["time"].split(":")[0]) * 60
        time += int(request.form["time"].split(":")[1])
        state = request.form["state"] == "on"
        schedule.rules.append(ScheduleRule(light=light, time=time, state=state))
        db.session.commit()
        return redirect(url_for("edit_schedule", schedule_id=schedule.id))

    return application


if __name__ == "__main__":
    application = create_application()
    application.run(host="0.0.0.0")
