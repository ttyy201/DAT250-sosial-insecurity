from datetime import timedelta
from flask import Flask, g, session
from flask import render_template, url_for, flash, request, redirect, Response
from config import Config
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user  
import sqlite3
import os

# create and configure app
app = Flask(__name__)
Bootstrap(app)
login_manager = LoginManager(app)
login_manager.login_view = 'index'
app.config.from_object(Config)
app.config.from_object(Config.ALLOWED_EXTENSION)


class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = int(id)
        self.username = username
        self.password = password
        self.authenticated = False
    def is_active(self):
        return self.is_active()
    def is_anonymous(self):
        return False
    def is_authenticated(self):
        return self.authenticated
    def is_active(self):
        return True
    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    curs = db.cursor()
    curs.execute("SELECT * from Users where id = (?)",[user_id])
    rv = curs.fetchone()
    if rv is None:
        return None
    else:
        return User(int(rv[0]),rv[1],rv[4])



# get an instance of the db
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

# initialize db for the first time
def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# perform generic query, not very secure yet
def query_db(query, one=False):
    db = get_db()
    cursor = db.execute(query)
    rv = cursor.fetchall()
    cursor.close()
    db.commit()
    return (rv[0] if rv else None) if one else rv

# TODO: Add more specific queries to simplify code

# automatically called when application is closed, and closes db connection
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# initialize db if it does not exist
if not os.path.exists(app.config['DATABASE']):
    init_db()

if not os.path.exists(app.config['UPLOAD_PATH']):
    os.mkdir(app.config['UPLOAD_PATH'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSION    



from app import routes
