from flask import Flask, make_response, redirect, request, Response, render_template, url_for, flash
from database import db_session
from decorators import login_required
from forms import AddCampaignForm
from flask_paginate import Pagination, get_page_parameter
import argparse
import config
import base64
import copy
import datetime
import getpass
import hashlib
import json
import os
import pymongo
import random
import string
import time

debug = True

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['MONGO_SERVER'] = 'localhost'
app.config['MONGO_DB'] = 'earl-pixel-tracker'

mongo_client = pymongo.MongoClient(app.config['MONGO_SERVER'], 27017, connect=False)
mongo_db = mongo_client[app.config['MONGO_DB']]


# clear all db sessions at the end of the request
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.route('/', methods=['GET'])
def homepage():
    return render_template(
        'index.html',
    )


@app.route('/index', methods=['GET'])
@login_required
def index():
    return redirect('/campaigns', 302)


@app.route('/campaign/add', methods=['GET', 'POST'])
@login_required
def add_campaign():
    form = AddCampaignForm(request.form)

    if request.method == 'POST' and form.validate_on_submit():

        event_record = {
            'job_number': form.job_number.data,
            'client_id': form.client_id.data,
            'campaign': form.campaign.data,
            'date_sent': datetime.datetime.now(),
            'sends': 0,
            'ip': None,
            'opens': 0
        }

        # hash our data and create the campaign event record
        campaign_hash = hashlib.sha1(event_record['campaign']).hexdigest()
        event_record['campaign_hash'] = campaign_hash
        campaign_collection = mongo_db['campaign_collection']
        campaign_collection.insert_one(event_record)
        flash('Campaign {} created successfully for {}'.format(campaign_hash, event_record['campaign']),
              category='success')
        return redirect(url_for('campaigns'))

    return render_template(
        'add_campaign.html',
        form=form
    )


@app.route('/leads', methods=['GET'])
@login_required
def leads():
    return render_template(
        'leads.html'
    )


@app.route('/reports', methods=['GET'])
@login_required
def reports():
    return render_template(
        'reports.html'
    )


@app.route("/login")
def login():
    return redirect('/auth/login', 302)


@app.route("/auth/login", methods=['GET', 'POST'])
def auth_login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username', None)
    password = request.form.get('password', None)

    user = get_user(username)

    if user and check_password(password, user['password']):
        token = hashlib.sha512(''.join([random.SystemRandom().choice(string.ascii_letters)
                                        for _ in range(1024)])).hexdigest()

        user_collection = mongo_db['auth_users']
        user_collection.update_one({'username': username}, {'$set': {'token': token, }})
        resp = make_response(redirect('/campaigns', 302))
        resp.set_cookie('token', token, 3600 * 24 * 30)

        return resp

    flash('Sorry, your login credentials have failed.  Please try again...', category='danger')
    return render_template('login.html')


@app.route('/logout', methods=['GET'])
def logout():
    resp = make_response(redirect('/campaigns', 302))
    resp.set_cookie('token', expires=0)
    flash('You have been successfully logged out.  Thank you!', category='info')
    return resp


def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ))


@app.template_filter('formatdate')
def format_date(value):
    dt = value
    return dt.strftime('%Y-%m-%d %H:%M')


def set_password(raw_password):
    algo = 'sha512'
    salt = os.urandom(128)
    encoded_salt = base64.b64encode(salt)
    hsh = hashlib.sha512('{}{}'.format(salt, raw_password)).hexdigest()
    return '{}:{}:{}'.format(algo, encoded_salt, hsh)


def check_password(raw_password, enc_password):
    algo, encoded_salt, hsh = enc_password.split(':')
    salt = base64.b64decode(encoded_salt)
    return hsh == hashlib.sha512('{}{}'.format(salt, raw_password)).hexdigest()


def get_user(username):
    user_collection = mongo_db['auth_users']
    return user_collection.find_one({'username': username})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EARL Web Frontend')
    parser.add_argument('command', nargs=1, choices=('run',))
    args = parser.parse_args()
    port = 5580

    if 'run' in args.command:
        app.run(
            debug=debug,
            port=port
        )
