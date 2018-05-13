from flask import Blueprint, url_for, session, redirect, render_template, current_app
from urllib2 import Request, urlopen, URLError
from flask_oauth import OAuth
import yaml
import functools
import json


def create_blueprint(test_config=None):
    configuration = yaml.load(open("config.yaml", "r"))
    if test_config is not None:
        configuration.update(test_config)

    bp = Blueprint("auth", __name__)

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

    def login_required(view):

        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if "access_token" not in session and not configuration["test"]:
                return render_template("login.html")

            return view(**kwargs)

        return wrapped_view

    bp.login_required = login_required

    @bp.route("/login")
    def login():
        callback = url_for("auth.authorized", _external=True)
        return google.authorize(callback=callback)

    @bp.route(configuration["redirect_uri"])
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
            current_app.logger.warn(
                "Unauthorised attempted access of / by %s", login_details["email"]
            )
            session.pop("access_token", None)
            return "<html><body>Sorry, you are not authorized.</body></html>"

        current_app.logger.info("Login by %s", login_details["email"])
        return redirect(url_for("index"))

    @google.tokengetter
    def get_access_token():
        return session.get("access_token")

    return bp
