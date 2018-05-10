from flask import (
    Flask,
    redirect,
    url_for,
    session,
    request,
    render_template,
    send_from_directory,
    redirect,
    flash,
    abort,
)
from flask_oauth import OAuth
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

    oauth = OAuth()
    google = oauth.remote_app(
        "google",
        base_url="https://www.google.com/accounts",
        authorize_url="https://accounts.google.com/o/oauth2/auth",
        request_token_url=None,
        request_token_params={
            "scope": "https://www.googleapis.com/auth/userinfo.email",
            "response_type": "code",
        },
        access_token_url="https://accounts.google.com/o/oauth2/token",
        access_token_method="POST",
        access_token_params={"grant_type": "authorization_code"},
        consumer_key=configuration["google_client_id"],
        consumer_secret=configuration["google_client_secret"],
    )

    @application.template_filter("strftime")
    def _jinja2_filter_datetime(date, fmt=None):
        native = datetime.fromtimestamp(date)
        format = "%X %d/%m/%Y"
        return native.strftime(format)

    @application.route("/")
    def index():
        if "access_token" not in session and not configuration["test"]:
            return render_template("login.html")

        return render_template(
            "index.html",
            data=open("/tmp/data").read(),
            lights=Light.query.all(),
            last_modified=os.path.getmtime("/tmp/data"),
        )

    @application.route("/edit/light/<light_id>", methods=["GET", "POST"])
    def edit_light(light_id):
        if "access_token" not in session and not configuration["test"]:
            return render_template("login.html")

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

    @application.route("/login")
    def login():
        callback = url_for("authorized", _external=True)
        return google.authorize(callback=callback)

    @application.route(configuration["redirect_uri"])
    @google.authorized_handler
    def authorized(resp):
        access_token = resp["access_token"]
        session["access_token"] = access_token, ""
        if access_token is None:
            return render_template("login.html")

        headers = {"Authorization": "OAuth " + access_token}
        req = Request("https://www.googleapis.com/oauth2/v1/userinfo", None, headers)
        try:
            res = urlopen(req)
        except URLError as e:
            if e.code == 401:
                session.pop("access_token", None)
                return render_template("login.html")

            return str(e)

        login_details = json.loads(res.read())

        if login_details["email"] not in configuration["authorized_emails"]:
            application.logger.warn(
                "Unauthorised attempted access of / by %s", login_details["email"]
            )
            session.pop("access_token", None)
            return "<html><body>Sorry, you are not authorized.</body></html>"

        application.logger.info("Login by %s", login_details["email"])
        return redirect(url_for("index"))

    @google.tokengetter
    def get_access_token():
        return session.get("access_token")

    @application.route("/state", methods=["POST"])
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

            if light.lightstates == [] or light.latest_state() != light_state:
                light.lightstates.append(
                    LightState(time=int(time.time()), state=light_state)
                )

            db.session.add(light)
            db.session.commit()
        open("/tmp/data", "w").write(str(request.get_json()))
        return "Good job!"

    return application


if __name__ == "__main__":
    application = create_application()
    application.run(host="0.0.0.0")
