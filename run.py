# MODULE IMPORTS

# Flask modules
from flask import Flask, render_template, request, url_for, request, redirect, abort,jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy

from flask_socketio import SocketIO, send

# Other modules
from urllib.parse import urlparse, urljoin
from datetime import datetime
import configparser
import json
import sys
import os
from os import environ
import requests

import stripe

# Local imports
from user import User, Anonymous
from message import Message
from note import Note
#from email_utility import send_registration_email, send_message_email
from verification import confirm_token

import user_forecast


# Create app
app = Flask(__name__)
socketio = SocketIO(app)

YOUR_DOMAIN = "http://localhost:8080"

# Configuration
config = configparser.ConfigParser()
config.read('configuration.ini')
default = config['DEFAULT']
app.secret_key = default['SECRET_KEY']
app.config['MONGO_DBNAME'] = default['DATABASE_NAME']
app.config['MONGO_URI'] = default['MONGO_URI']
app.config['PREFERRED_URL_SCHEME'] = "https"
app.config['SQLALCHEMY_DATABASE_URI'] = environ.get(
    'DATABASE_URL', 'sqlite:///ETL/output_file/maternal_mortality.sqlite')

stripe.api_key = 'sk_test_51LsJotSB8P98qa61NxqfyPqz0Yt5n15J4s6YIyn9Y2KVcrI0we14TAgH8Lh8blv2tKsKtV4GX27XPSUiP2x41USU00zqe6rW09'
# Create Pymongo
mongo = PyMongo(app)

db = SQLAlchemy(app)

# Create Bcrypt
bc = Bcrypt(app)

# Create login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.anonymous_user = Anonymous
login_manager.login_view = "login"


# Create table schema
class Global(db.Model):
    __tablename__ = 'mmr_global'
    name = db.Column(db.String)
    id = db.Column(db.String, primary_key=True)
    mmr = db.Column(db.Integer)
    ranking = db.Column(db.Integer)
    category = db.Column(db.String)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)


class Causes(db.Model):
    __tablename__ = 'causes_of_deaths'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(255))
    abortion = db.Column(db.Integer)
    embolism = db.Column(db.Integer)
    haemorrhage = db.Column(db.Integer)
    hypertension = db.Column(db.Integer)
    sepsis = db.Column(db.Integer)
    other_direct_causes = db.Column(db.Integer)
    indirect_causes = db.Column(db.Integer)


class CDC(db.Model):
    __tablename__ = 'mmr_us'
    record_id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(255))
    id = db.Column(db.Integer)
    state_code = db.Column(db.Integer)
    year = db.Column(db.Integer)
    deaths = db.Column(db.Integer)
    births = db.Column(db.Integer)
    maternal_mortality_ratio = db.Column(db.Float)
    population = db.Column(db.Integer)


class Playground(db.Model):
    __tablename__ = 'user_input'
    __table_args__ = {'extend_existing': True}
    year = db.Column(db.String, primary_key=True)
    maternal_mortality_ratio = db.Column(db.Float)


class Forecast(db.Model):
    __tablename__ = 'ten_year_forecast'
    __table_args__ = {'extend_existing': True}
    year = db.Column(db.String, primary_key=True)
    mmr_prediction = db.Column(db.Float)
    maternal_mortality_ratio = db.Column(db.Float)
    diabetes_val = db.Column(db.Float)
    prem_death_val = db.Column(db.Float)
    phys_inac_val = db.Column(db.Float)
    low_birthweight_val = db.Column(db.Float)
    obesity_val = db.Column(db.Float)
    cardio_death_val = db.Column(db.Float)
    medicare = db.Column(db.Float)
    cancer_death_val = db.Column(db.Float)
    chlamydia_val = db.Column(db.Float)
    child_pov_val = db.Column(db.Float)
    smoking_val = db.Column(db.Float)
    infant_mort_val = db.Column(db.Float)
    income_ineq_val = db.Column(db.Float)
    dentists_val = db.Column(db.Float)
    prem_death_ri_val = db.Column(db.Float)
    dent_vis_val = db.Column(db.Float)
    all_outcomes_val = db.Column(db.Float)
    all_determs_val = db.Column(db.Float)
    health_stat_fem_val = db.Column(db.Float)
    population = db.Column(db.Float)
    employer = db.Column(db.Float)
    non_group = db.Column(db.Float)
    medicaid = db.Column(db.Float)
    military = db.Column(db.Float)
    uninsured = db.Column(db.Float)
    air_pollution_val = db.Column(db.Float)
    choles_check_val = db.Column(db.Float)
    drug_deaths_val = db.Column(db.Float)
    immun_child_val = db.Column(db.Float)
    infect_dis_val = db.Column(db.Float)
    uninsured_val = db.Column(db.Float)
    teen_birth_val = db.Column(db.Float)
    primary_care_val = db.Column(db.Float)

# ROUTES

# Index
@app.route('/')
def index():
    return render_template('index.html')


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if current_user.is_authenticated:
            # Redirect to index if already authenticated
            return redirect(url_for('/index'))
        # Render login page
        return render_template('login.html', error=request.args.get("error"))
    # Retrieve user from database
    users = mongo.db.users
    user_data = users.find_one({'email': request.form['email']}, {'_id': 0})
    if user_data:
        # Check password hash
        if bc.check_password_hash(user_data['password'], request.form['pass']):
            # Create user object to login (note password hash not stored in session)
            user = User.make_from_dict(user_data)
            login_user(user)

            # Check for next argument (direct user to protected page they wanted)
            next = request.args.get('next')
            if not is_safe_url(next):
                return abort(400)

            # Go to profile page after login
            return redirect(next or url_for('profile'))

    # Redirect to login page on error
    return redirect(url_for('login', error=1))



@app.route('/success',methods=['GET'])
def success():
    return render_template("success.html")

@app.route('/cancel',methods=['GET'])
def cancel():
    return render_template("cancel.html")    

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': 'price_1LsJv5SB8P98qa619o60ivDF',
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=YOUR_DOMAIN + '/success',
            cancel_url=YOUR_DOMAIN + '/cancel',
        )
    except Exception as e:
        return str(e)
 
    return redirect(checkout_session.url, code=303)

# Register
@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        # Trim input data
        email = request.form['email'].strip()
        title = request.form['title'].strip()
        blood = request.form['blood'].strip()
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        address = request.form['address'].strip()
        contacts = request.form['numbers'].strip()
        password = request.form['pass'].strip()

        users = mongo.db.users
        # Check if email address already exists
        existing_user = users.find_one(
            {'email': email}, {'_id': 0})

        if existing_user is None:
            logout_user()
            # Hash password
            hashpass = bc.generate_password_hash(password).decode('utf-8')
            # Create user object (note password hash not stored in session)
            new_user = User(title,blood, first_name, last_name, email,address,contacts)
            # Create dictionary data to save to database
            user_data_to_save = new_user.dict()
            user_data_to_save['password'] = hashpass
            print(user_data_to_save)

            # Insert user record to database
            if users.insert_one(user_data_to_save):
                login_user(new_user)
                #send_registration_email(new_user)
                return redirect(url_for('profile'))
            else:
                # Handle database error
                return redirect(url_for('register', error=2))

        # Handle duplicate email
        return redirect(url_for('register', error=1))

    # Return template for registration page if GET request
    return render_template('register.html', error=request.args.get("error"))


# Confirm email
@app.route('/confirm/<token>', methods=['GET'])
def confirm_email(token):
    logout_user()
    try:
        email = confirm_token(token)
        if email:
            if mongo.db.users.update_one({"email": email}, {"$set": {"verified": True}}):
                return render_template('confirm.html', success=True)
    except:
        return render_template('confirm.html', success=False)
    else:
        return render_template('confirm.html', success=False)


# Verification email
@app.route('/verify', methods=['POST'])
@login_required
def send_verification_email():
    if current_user.verified == False:
        #send_registration_email(current_user)
        return "Verification email sent"
    else:
        return "Your email address is already verified"


# Profile
@app.route('/profile', methods=['GET'])
@login_required
def profile():
    notes = mongo.db.notes.find(
        {"user_id": current_user.id, "deleted": False}).sort("timestamp", -1)
    return render_template('profile.html', notes=list(notes),title=current_user.title)

@app.route('/stats', methods=['GET'])
@login_required
def stats():
    return render_template('world.html')

@app.route('/community', methods=['GET'])
@login_required
def community():
    articles = mongo.db.notes.find(
        {"deleted": False}).sort("timestamp", -1)
    return render_template('community.html', articles=list(articles),title=current_user.title)


@app.route("/api/user-forecast", methods=['GET', 'POST'])
def playgroundForecast():

    if request.method == "POST":
        data = request.get_json()
        # print(data)
        diabetes = float(data['diabetes'] or 9.7)
        prem_death = float(data['prem_death'] or 7546)
        phys_inac = float(data['phys_inac'] or 24.6)
        low_birthweight = float(data['low_birthweight'] or 8.1)
        health_stat_fem = float(data['health_stat_fem'] or 52.1)

        user_predicted_mmr = user_forecast.forecast_graph(
            diabetes, prem_death, phys_inac, low_birthweight, health_stat_fem)

    return jsonify(user_predicted_mmr)


@app.route('/machine-learning-playground')
def ml_playground():
    return render_template('machine-learning-playground.html')

@app.route("/api/user-input")
def userInput():
    tasks = db.session.query(Playground)
    playground_data = []

    for task in tasks:
        item = {
            'year': task.year,
            'mmr': task.maternal_mortality_ratio,
        }
        playground_data.append(item)

    return jsonify(playground_data)

@app.route('/midwife', methods=['GET'])
@login_required
def midwife():
    return render_template('midwife.html')

@app.route('/chat',methods=['GET'])
@login_required
def chat():
    return render_template('chat.html')

def messageReceived(methods=['GET', 'POST']):
    print('message was received!!!')

@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print('received my event: ' + str(json))
    socketio.emit('my response', json, callback=messageReceived)


@app.route('/api/mmr-global')
def getGlobaldata():
    tasks = db.session.query(Global)
    mmr_global_data = []

    for task in tasks:
        item = {
            'name': task.name,
            'id': task.id,
            'mmr': task.mmr,
            'ranking': task.ranking,
            'category': task.category,
            'geometry': {
                'lat': task.latitude,
                'lng': task.longitude
            },
        }
        mmr_global_data.append(item)

    return jsonify(mmr_global_data)


@app.route('/api/causes-of-deaths')
def getCausesdata():
    tasks = db.session.query(Causes)
    causes_data = []

    for task in tasks:
        item = {
            'id': task.id,
            'region': task.region,
            'abortion': task.abortion,
            'embolism': task.embolism,
            'haemorrhage': task.haemorrhage,
            'hypertension': task.hypertension,
            'sepsis': task.sepsis,
            'other_direct_causes': task.other_direct_causes,
            'indirect_causes': task.indirect_causes
        }
        causes_data.append(item)

    return jsonify(causes_data)


@app.route('/api/mmr-us')
def getUSdata():
    tasks = db.session.query(CDC)
    mmr_us_data = []

    for task in tasks:
        item = {
            'record_id': task.record_id,
            'state': task.state,
            'id': task.id,
            'state_code': task.state_code,
            'year': task.year,
            'deaths': task.deaths,
            'births': task.births,
            'mmr': task.maternal_mortality_ratio,
            'population': task.population
        }
        mmr_us_data.append(item)

    return jsonify(mmr_us_data)

#Bot
@app.route("/bothook")
def get_bot_response():
    msg = request.args.get('msg')
    r=requests.post('http://localhost:5005/webhooks/rest/webhook',json={"message":msg})
    print('Bot says, ',end=' ')
    response=''
    for i in r.json():
        response+=i['text']
    return response


# Messages
@app.route('/messages', methods=['GET'])
@login_required
def messages():
    all_users = mongo.db.users.find(
        {"id": {"$ne": current_user.id}}, {'_id': 0})
    inbox_messages = mongo.db.messages.find(
        {"to_id": current_user.id, "deleted": False}).sort("timestamp", -1)
    sent_messages = mongo.db.messages.find(
        {"from_id": current_user.id, "deleted": False, "hidden_for_sender": False}).sort("timestamp", -1)
    return render_template('messages.html', users=all_users, inbox_messages=inbox_messages, sent_messages=sent_messages)


# Logout
@app.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/food', methods=['GET'])
@login_required
def food():
    return render_template("food.html")

@app.route('/music', methods=['GET'])
@login_required
def music():
    return render_template("music.html")

@app.route('/art', methods=['GET'])
@login_required
def art():
    return render_template("art.html")

@app.route('/yoga', methods=['GET'])
@login_required
def yoga():
    return render_template("yoga.html")

@app.route('/meds', methods=['GET'])
@login_required
def meds():
    return render_template("meds.html")

@app.route('/product', methods=['GET'])
@login_required
def product():
    return render_template("product.html")

# POST REQUEST ROUTES

# Add note
@app.route('/add_note', methods=['POST'])
@login_required
def add_note():
    title = request.form.get("title")
    body = request.form.get("body")
    user_id = current_user.id
    user_name = current_user.display_name()
    note = Note(title, body, user_id, user_name)
    if mongo.db.notes.insert_one(note.dict()):
        return "Success! Note added: " + title
    else:
        return "Error! Could not add note"


# Delete note
@app.route('/delete_note', methods=['POST'])
@login_required
def delete_note():
    note_id = request.form.get("note_id")
    if mongo.db.notes.update_one({"id": note_id}, {"$set": {"deleted": True}}):
        return "Success! Note deleted"
    else:
        return "Error! Could not delete note"

@app.route('/articles', methods=['GET'])
@login_required
def articles():
    return render_template("articles.html")
# Send message
'''@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    title = request.form.get("title")
    body = request.form.get("body")
    from_id = current_user.id
    from_name = current_user.display_name()
    to_id = request.form.get("user")
    to_user_dict = mongo.db.users.find_one({"id": to_id})
    to_user = User.make_from_dict(to_user_dict)
    to_name = to_user.display_name()
    message = Message(title, body, from_id, from_name, to_id, to_name)
    if mongo.db.messages.insert_one(message.dict()):
        send_message_email(from_user=current_user,
                           to_user=to_user, message=message)
        return "Success! Message sent to " + to_name + ": " + title
    else:
        return "Error! Could not send message"'''


# Delete message
@app.route('/delete_message', methods=['POST'])
@login_required
def delete_message():
    message_id = request.form.get("message_id")
    if mongo.db.messages.update_one({"id": message_id}, {"$set": {"deleted": True}}):
        return "Success! Message deleted"
    else:
        return "Error! Could not delete message"


# Hide sent message
@app.route('/hide_sent_message', methods=['POST'])
@login_required
def hide_sent_message():
    message_id = request.form.get("message_id")
    if mongo.db.messages.update_one({"id": message_id}, {"$set": {"hidden_for_sender": True}}):
        return "Success! Message hidden from sender"
    else:
        return "Error! Could not hide message"


# Change Name
@app.route('/change_name', methods=['POST'])
@login_required
def change_name():
    title = request.form['title'].strip()
    first_name = request.form['first_name'].strip()
    last_name = request.form['last_name'].strip()

    if mongo.db.users.update_one({"email": current_user.email}, {"$set": {"title": title, "first_name": first_name, "last_name": last_name}}):
        return "User name updated successfully"
    else:
        return "Error! Could not update user name"


# Delete Account
@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = current_user.id

    # Deletion flags
    user_deleted = False
    notes_deleted = False
    messages_deleted = False

    # Delete user details
    if mongo.db.users.delete_one({"id": user_id}):
        user_deleted = True
        logout_user()

    # Delete notes
    if mongo.db.notes.delete_many({"user_id": user_id}):
        notes_deleted = True

    # Delete messages
    if mongo.db.messages.delete_many({"$or": [{"from_id": user_id}, {"to_id": user_id}]}):
        messages_deleted = True

    return {"user_deleted": user_deleted, "notes_deleted": notes_deleted, "messages_deleted": messages_deleted}


# LOGIN MANAGER REQUIREMENTS

# Load user from user ID
@login_manager.user_loader
def load_user(userid):
    # Return user object or none
    users = mongo.db.users
    user = users.find_one({'id': userid}, {'_id': 0})
    if user:
        return User.make_from_dict(user)
    return None

# Safe URL
def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


# Heroku environment
if os.environ.get('APP_LOCATION') == 'heroku':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
else:
    app.run(host='localhost', port=8080, debug=True)
