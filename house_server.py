from flask import Flask, redirect, url_for, session, request, render_template, send_from_directory
from flask_oauth import OAuth
from urllib2 import Request, urlopen, URLError
import json
import yaml

configuration = yaml.load(open('config.yaml', 'r'))

application = Flask(__name__)
application.debug = True
application.secret_key = "laekdfjlkajsfpwiejr1oj3204-1044"

oauth = OAuth()
google = oauth.remote_app('google',
    base_url='https://www.google.com/accounts',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    request_token_url=None,
    request_token_params={'scope': 'https://www.googleapis.com/auth/userinfo.email',
                          'response_type': 'code'},
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_method='POST',
    access_token_params={'grant_type': 'authorization_code'},
    consumer_key=configuration['google_client_id'],
    consumer_secret=configuration['google_client_secret'])

@application.route("/")
def index():
  access_token = session.get('access_token')
  if access_token is None:
    return render_template('login.html')
  access_token = access_token[0]
  headers = {"Authorization": "OAuth "+access_token}
  req = Request("https://www.googleapis.com/oauth2/v1/userinfo",
      None, headers)
  try:
    res = urlopen(req)
  except URLError, e:
    if e.code == 401:
      session.pop('access_token', None)
      return render_template('login.html')
    return str(e)
  login_details = json.loads(res.read())
  if login_details['email'] not in configuration['authorized_emails']:
    return "<html><body>Sorry, you are not authorized.</body></html>"
  return render_template('index.html', data=open("/tmp/data").read()+"DDD")


@application.route("/login")
def login():
  callback=url_for('authorized', _external=True)
  return google.authorize(callback=callback)

@application.route(configuration['redirect_uri'])
@google.authorized_handler
def authorized(resp):
  access_token = resp['access_token']
  session['access_token'] = access_token, ''
  return redirect(url_for('index'))

@google.tokengetter
def get_access_token():
  return session.get('access_token')

@application.route('/state', methods=["POST"])
def state():
  open('/tmp/data','w').write(str(request.get_json(force=True)))
  return "Good job!"

if __name__ == "__main__":
	application.run(host="0.0.0.0")
