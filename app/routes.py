#from ast import Not
from urllib.request import Request
from wsgiref import validate
from flask import Flask, render_template, flash, redirect, url_for, request, session, g
from flask_login import login_user, current_user, logout_user, login_required
from app import allowed_file, app, get_db, load_user, query_db
from app.forms import IndexForm, PostForm, FriendsForm, ProfileForm, CommentsForm
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
import os

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)


# this file contains all the different routes, and the logic for communicating with the database

# home page/login/registration

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@limiter.limit("1000 per minute")
def index():
    form = IndexForm()
    if current_user.is_authenticated:
        return redirect(url_for('stream'))
    if form.login.is_submitted() and form.login.submit.data:
        db = get_db()
        curs = db.cursor()
        curs.execute("SELECT * from Users where username = (?)",[form.login.username.data])
        user = list(curs.fetchone())
        Us = load_user(user[0])
        if user == None:
            flash('Sorry, this user does not exist!')
        elif form.login.username.data == Us.username and check_password_hash(Us.password, form.login.password.data):
            session["username"] = Us.username
            login_user(Us, remember=form.login.remember_me.data)
            flash('Login succsessfull')
            return redirect(url_for('stream'))
        else:
            flash('Sorry, wrong username or password!')

    elif form.register.is_submitted() and form.register.submit.data and form.register.first_name.validate(request.form) and form.register.username.validate(request.form) and form.register.password.validate(request.form):
        password = form.register.password.data
        passord = generate_password_hash(password, method="sha256")
        if form.register.password.data != form.register.confirm_password.data:
            flash('Password did not match.')
            return redirect(url_for('index'))
        query_db('INSERT INTO Users (username, first_name, last_name, password) VALUES("{}", "{}", "{}", "{}");'.format(form.register.username.data, form.register.first_name.data,
         form.register.last_name.data, passord))
        flash('New user created')
        return redirect(url_for('index'))
    return render_template('index.html', title='Welcome', form=form)


# content stream page
@app.route('/stream', methods=['GET', 'POST'])
@login_required
def stream():
    form = PostForm()
    user = query_db('SELECT * FROM Users WHERE username="{}";'.format(session.get("username", None)), one=True)
    # if session.get("username", None) == None:
    #     return redirect(url_for('index'))
    if form.is_submitted() and (form.content.validate(request.form) or form.image.validate(request.form)):
        if form.image.data and allowed_file(form.image.data.filename):
            path = os.path.join(app.config['UPLOAD_PATH'],secure_filename(form.image.data.filename))
            form.image.data.save(path)

        query_db('INSERT INTO Posts (u_id, content, image, creation_time) VALUES({}, "{}", "{}", \'{}\');'.format(user['id'], form.content.data, form.image.data.filename, datetime.now()))
        return redirect(url_for('stream', username=session.get("username", None)))

    posts = query_db('SELECT p.*, u.*, (SELECT COUNT(*) FROM Comments WHERE p_id=p.id) AS cc FROM Posts AS p JOIN Users AS u ON u.id=p.u_id WHERE p.u_id IN (SELECT u_id FROM Friends WHERE f_id={0}) OR p.u_id IN (SELECT f_id FROM Friends WHERE u_id={0}) OR p.u_id={0} ORDER BY p.creation_time DESC;'.format(user['id']))
    return render_template('stream.html', title='Stream', username=session.get("username", None), form=form, posts=posts)

@app.before_request
def before_request():
    session.permanent=True
    app.permanent_session_lifetime = timedelta(minutes=20)
    session.modified = True

# comment page for a given post and user.
@app.route('/comments/<int:p_id>', methods=['GET', 'POST'])
@login_required
def comments(p_id):
    form = CommentsForm()
    # if session.get("username", None) == None:
    #     return redirect(url_for('index'))
    if form.is_submitted() and form.comment.validate(request.form):
        user = query_db('SELECT * FROM Users WHERE username="{}";'.format(session.get("username", None)), one=True)
        query_db('INSERT INTO Comments (p_id, u_id, comment, creation_time) VALUES({}, {}, "{}", \'{}\');'.format(p_id, user['id'], form.comment.data, datetime.now()))

    post = query_db('SELECT * FROM Posts WHERE id={};'.format(p_id), one=True)
    all_comments = query_db('SELECT DISTINCT * FROM Comments AS c JOIN Users AS u ON c.u_id=u.id WHERE c.p_id={} ORDER BY c.creation_time DESC;'.format(p_id))
    return render_template('comments.html', title='Comments', username=session.get("username", None), form=form, post=post, comments=all_comments)

# page for seeing and adding friends
@app.route('/friends', methods=['GET', 'POST'])
@login_required
def friends():
    form = FriendsForm()
    user = query_db('SELECT * FROM Users WHERE username="{}";'.format(session.get("username", None)), one=True)
    # if session.get("username", None) == None:
    #     return redirect(url_for('index'))
    if form.is_submitted():
        friend = query_db('SELECT * FROM Users WHERE username="{}";'.format(form.username.data), one=True)
        if friend is None:
            flash('User does not exist')
        else:
            query_db('INSERT INTO Friends (u_id, f_id) VALUES({}, {});'.format(user['id'], friend['id']))
    
    all_friends = query_db('SELECT * FROM Friends AS f JOIN Users as u ON f.f_id=u.id WHERE f.u_id={} AND f.f_id!={} ;'.format(user['id'], user['id']))
    return render_template('friends.html', title='Friends', username=session.get("username", None), friends=all_friends, form=form)

# see and edit detailed profile information of a user
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    # if session.get("username", None) == None:
    #     return redirect(url_for('index'))
    if form.is_submitted():
        query_db('UPDATE Users SET education="{}", employment="{}", music="{}", movie="{}", nationality="{}", birthday=\'{}\' WHERE username="{}" ;'.format(
            form.education.data, form.employment.data, form.music.data, form.movie.data, form.nationality.data, form.birthday.data, session.get("username", None)
        ))
        return redirect(url_for('profile', username=session.get("username", None)))
    
    user = query_db('SELECT * FROM Users WHERE username="{}";'.format(session.get("username", None)), one=True)
    return render_template('profile.html', title='profile', username=session.get("username", None), user=user, form=form)

@app.route("/logout")
def logout():
    logout_user()
    session.pop("username")
    flash('Logged out.')
    return redirect(url_for("index"))