from flask import Flask, json, request, make_response, session, redirect
from flask_sqlalchemy import SQLAlchemy
import os
import functools

from authlib.client import OAuth2Session
import google.oauth2.credentials
import googleapiclient.discovery

ACCESS_TOKEN_URI = 'https://www.googleapis.com/oauth2/v4/token'
AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&prompt=consent'

AUTHORIZATION_SCOPE = 'openid email profile'

AUTH_REDIRECT_URI = os.environ.get("FN_AUTH_REDIRECT_URI", default=False)
BASE_URI = os.environ.get("FN_BASE_URI", default=False)
CLIENT_ID = os.environ.get("FN_CLIENT_ID", default=False)
CLIENT_SECRET = os.environ.get("FN_CLIENT_SECRET", default=False)

AUTH_TOKEN_KEY = 'auth_token'
AUTH_STATE_KEY = 'auth_state'
USER_INFO_KEY = 'user_info'

app = Flask(__name__)
app.secret_key = os.environ.get("FN_FLASK_SECRET_KEY", default=False)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Movie(db.Model):
    __tablename__ = 'movie'
    id = db.Column(db.Integer, nullable=False, primary_key=True)
    name = db.Column(db.Text)

    def __repr__(self):
        return '<Movie {} {}>'.format(self.id, self.name)

    def to_dict(self):
        dictMovie = {}
        dictMovie['id'] = self.id
        dictMovie['name'] = self.name
        return dictMovie


@app.route('/api/movies', methods=['GET'])
def movies_get():
    movies = Movie.query.all()
    return json.dumps([_.to_dict() for _ in movies])


@app.route('/api/movies', methods=['POST'])
def movies_post():
    movie_req = request.get_json()
    if movie_req:
        movie = Movie(name=movie_req.get('name'))
        try:
            db.session.add(movie)
            db.session.commit()
            return json.dumps(movie.to_dict())
        except Exception:
            db.session.rollback()
            return json.dumps(None)
    return json.dumps(None)


@app.route('/api/movies', methods=['DELETE'])
def movies_delete():
    try:
        num_rows_del = db.session.query(Movie).delete()
        db.session.commit()
        return json.dumps({'num_rows_del': num_rows_del})
    except Exception:
        db.session.rollback()
        return json.dumps(None)


@app.route('/api/movies/<int:id>', methods=['GET'])
def movies_id_get(id):
    movie = Movie.query.filter_by(id=id).first()
    if movie:
        return json.dumps(movie.to_dict())
    return json.dumps(None)


@app.route('/api/movies/<int:id>', methods=['DELETE'])
def movies_id_delete(id):
    try:
        Movie.query.filter_by(id=id).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
    return json.dumps(None)


@app.route('/')
def index():
    if is_logged_in():
        user_info = get_user_info()
        return 'You are currently logged in as ' + user_info['given_name']

    return 'You are not currently logged in'


def no_cache(view):
    @functools.wraps(view)
    def no_cache_impl(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers[
            'Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return functools.update_wrapper(no_cache_impl, view)


@app.route('/google/login')
@no_cache
def login():
    my_session = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=AUTHORIZATION_SCOPE,
        redirect_uri=AUTH_REDIRECT_URI)
    uri, state = my_session.authorization_url(AUTHORIZATION_URL)
    session[AUTH_STATE_KEY] = state
    session.permanent = True
    return redirect(uri, code=302)


@app.route('/google/auth')
@no_cache
def google_auth_redirect():
    state = request.args.get('state', default=None, type=None)

    my_session = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=AUTHORIZATION_SCOPE,
        state=state,
        redirect_uri=AUTH_REDIRECT_URI)
    oauth2_tokens = my_session.fetch_access_token(
        ACCESS_TOKEN_URI, authorization_response=request.url)
    session[AUTH_TOKEN_KEY] = oauth2_tokens

    return redirect(BASE_URI, code=302)


@app.route('/google/logout')
@no_cache
def logout():
    session.pop(AUTH_TOKEN_KEY, None)
    session.pop(AUTH_STATE_KEY, None)
    session.pop(USER_INFO_KEY, None)

    return redirect(BASE_URI, code=302)


def is_logged_in():
    return True if AUTH_TOKEN_KEY in session else False


def build_credentials():
    if not is_logged_in():
        raise Exception('User must be logged in')

    oauth2_tokens = session[AUTH_TOKEN_KEY]
    return google.oauth2.credentials.Credentials(
        oauth2_tokens['access_token'],
        refresh_token=oauth2_tokens['refresh_token'],
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri=ACCESS_TOKEN_URI)


def get_user_info():
    credentials = build_credentials()
    oauth2_client = googleapiclient.discovery.build(
        'oauth2', 'v2', credentials=credentials)
    return oauth2_client.userinfo().get().execute()
