from urllib.request import Request, urlopen
from urllib.error import URLError
import functools
import json

from flask import (
    Blueprint, url_for, session, redirect, render_template, current_app, abort, request
)

from authlib.integrations.flask_client import OAuth

import yaml


def create_blueprint(test_config=None, app=None):
    configuration = yaml.safe_load(open("config.yaml", "r"))
    if test_config is not None:
        configuration.update(test_config)

    bp = Blueprint("auth", __name__)

    oauth = OAuth(app)
    google = oauth.register(
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
        client_id=configuration["google_client_id"],
        client_secret=configuration["google_client_secret"],
        client_kwargs={"scope": "https://www.googleapis.com/auth/userinfo.email"},
        userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
    )

    def login_required(view):

        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if "access_token" not in session and not configuration["test"]:
                return render_template("login.html")

            return view(**kwargs)

        return wrapped_view

    def pi_auth_required(view):

        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if request.args.get("key") != configuration["pi_key"]:
                abort(400)

            return view(**kwargs)

        return wrapped_view

    bp.login_required = login_required
    bp.pi_auth_required = pi_auth_required

    @bp.route("/login")
    def login():
        callback = url_for("auth.authorized", _external=True)
        return google.authorize_redirect(callback)

    @bp.route(configuration["redirect_uri"])
    def authorized():
        access_token = oauth.google.authorize_access_token()
        userinfo = oauth.google.userinfo()

        session["access_token"] = access_token, ""
        if userinfo.email not in configuration["authorized_emails"]:
            current_app.logger.warn(
                "Unauthorised attempted access of / by %s", userinfo.email
            )
            session.pop("access_token", None)
            return "<html><body>Sorry, you are not authorized.</body></html>"

        current_app.logger.info("Login by %s", userinfo.email)
        return redirect(url_for("index"))

    def get_access_token():
        return session.get("access_token")

    return bp
