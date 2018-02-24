from flask import Flask, make_response, redirect, request, Response, render_template, url_for, flash, g
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy, Pagination
from sqlalchemy import text, and_, exc
from database import db_session
from models import User, Store, Campaign, CampaignType, Visitor, AppendedVisitor, Lead, PixelTracker
from forms import AddCampaignForm, UserLoginForm, AddStoreForm, ApproveCampaignForm, CampaignCreativeForm, \
    ReportFilterForm
import argparse
import config
import datetime
import hashlib
import json
import os
import pymongo
import random
import string
import time

debug = False

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['MONGO_SERVER'] = config.MONGO_SERVER
app.config['MONGO_DB'] = config.MONGO_DB

# SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS
db = SQLAlchemy(app)

# Mongo DB
mongo_client = pymongo.MongoClient(app.config['MONGO_SERVER'], 27017, connect=False)
mongo_db = mongo_client[app.config['MONGO_DB']]

# define our login_manager
login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = "login"

# set the current date time for each page
today = datetime.datetime.now().strftime('%c')


# clear all db sessions at the end of each request
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


# load the user
@login_manager.user_loader
def load_user(id):
    try:
        return User.query.get(int(id))
    except exc.SQLAlchemyError as err:
        return None


# run before each request
@app.before_request
def before_request():
    g.user = current_user


# default routes
@app.route('/', methods=['GET'])
@app.route('/index', methods=['GET'])
@login_required
def index():
    return render_template(
        'index.html',
        current_user=current_user,
        today=today
    )


@app.route('/stores', methods=['GET'])
@login_required
def stores():
    """
    Get a list of active stores
    :param none
    :return: store list
    """
    store_count = 0

    stores = Store.query.filter(
        Store.status == 'Active'
    ).all()

    if stores:
        store_count = len(stores)

    return render_template(
        'stores.html',
        stores=stores,
        store_count=store_count,
        today=today
    )


@app.route('/store/<int:store_pk_id>', methods=['GET', 'POST'])
def store_detail(store_pk_id):
    """
    Get the store details by Store ID
    :param store_pk_id:
    :return: store obj
    """

    store = Store.query.filter(
        Store.id == store_pk_id
    ).one()

    campaigns = Campaign.query.order_by(
        Campaign.created_date.desc()
    ).filter(
        Campaign.store_id == store_pk_id
    ).limit(100).all()

    form = AddStoreForm(request.form)

    if request.method == 'POST' and form.validate_on_submit():

        # update our instance of store
        store.client_id = form.client_id.data
        store.status = form.status.data
        store.name = form.name.data
        store.address1 = form.address1.data
        store.address2 = form.address2.data
        store.city = form.city.data
        store.state = form.state.data.upper()
        store.zip_code = form.zip_code.data
        store.phone_number = form.phone_number.data
        store.adf_email = form.adf_email.data
        store.notification_email = form.notification_email.data
        store.reporting_email = form.reporting_email.data
        store.simplifi_client_id = form.simplifi_client_id.data
        store.simplifi_company_id = form.simplifi_company_id.data
        store.simplifi_name = form.simplifi_name.data

        # commit to the database
        db_session.commit()

        flash('The store details were saved successfully...', category='success')
        return redirect(url_for('store_detail', store_pk_id=store.id))

    return render_template(
        'store_detail.html',
        store=store,
        campaigns=campaigns,
        today=today,
        form=form
    )


@app.route('/store/add', methods=['GET', 'POST'])
def store_add():
    """
    Create a new store from the web data form
    :return: store ID
    """

    form = AddStoreForm(request.form)
    
    if request.method == 'POST' and form.validate_on_submit():
        
        new_store = Store(
            client_id=form.client_id.data,
            name=form.name.data,
            address1=form.address1.data,
            address2=form.address2.data,
            city=form.city.data,
            state=form.state.data.upper(),
            zip_code=form.zip_code.data,
            status=form.status.data,
            phone_number=form.phone_number.data,
            notification_email=form.notification_email.data,
            reporting_email=form.reporting_email.data
        )

        db_session.add(new_store)
        db_session.commit()

        return redirect(url_for('store_detail', store_pk_id=new_store.id))

    return render_template(
        'store_add.html',
        form=form,
        today=today
    )


@app.route('/campaigns', methods=['GET'])
@login_required
def campaigns():
    """
    Get a list of active campaigns
    :return: campaign list
    """
    campaign_count = 0

    campaigns = Campaign.query.order_by(
        Campaign.created_date.desc()).filter(
        Campaign.status == 'Active'
    ).limit(100).all()

    if campaigns:
        campaign_count = len(campaigns)

    return render_template(
        'campaigns.html',
        campaigns=campaigns,
        campaign_count=campaign_count,
        today=today
    )


@app.route('/campaign/<int:campaign_pk_id>', methods=['GET', 'POST'])
@login_required
def campaign_detail(campaign_pk_id):
    """
    The Campaign Detail view
    :param campaign_pk_id:
    :return: campaign
    """
    visitors_per_page = 20
    page = request.args.get('page', 1, type=int)
    form = AddCampaignForm()
    approval_form = ApproveCampaignForm()
    creative_form = CampaignCreativeForm()

    # first, get our campaign
    campaign = Campaign.query.filter(
        Campaign.id == campaign_pk_id
    ).one()

    if request.method == 'POST':

        if 'save-campaign-settings' in request.form.keys() and form.validate_on_submit():

            # update the campaign data
            campaign.job_number = form.job_number.data
            campaign.client_id = form.client_id.data
            campaign.radius = form.radius.data
            campaign.start_date = form.start_date.data
            campaign.end_data = form.end_date
            campaign.name = form.name.data
            campaign.status = form.status.data

            db_session.commit()

            flash('Campaign {} Settings were updated successfully'.format(campaign.name), category='success')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id))

        elif 'save-campaign-approval' in request.form.keys() and approval_form.validate_on_submit():
            campaign.options = approval_form.options.data
            campaign.description = approval_form.description.data
            campaign.funded = approval_form.funded.data
            campaign.approved = approval_form.approved.data
            if campaign.approved:
                campaign.approved_by = current_user.get_id()
            campaign.objective = approval_form.objective.data
            campaign.frequency = approval_form.frequency.data

            db_session.commit()

            flash('Campaign {} Approval was updated successfully'.format(campaign.name), category='info')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id))

        elif 'save-campaign-creative' in request.form.keys() and creative_form.validate_on_submit():
            campaign.creative_header = creative_form.creative_header.data
            campaign.creative_footer = creative_form.creative_footer.data
            db_session.commit()

            # flash a success message
            flash('Campaign {} Creative was saved successfully'.format(campaign.name), category='info')

    if campaign:

        visitors = Visitor.query.filter(and_(
            Visitor.job_number == campaign.job_number,
            Visitor.campaign_id == campaign.id
        )).all()

        store = Store.query.filter(
            Store.id == campaign.store_id
        ).one()

        if campaign.pixeltrackers_id:
            pt = PixelTracker.query.get(campaign.pixeltrackers_id)

        stmt = text("SELECT v.id, av.* from visitors v, appendedvisitors av where v.id = av.visitor "
                    "and v.store_id={} and v.campaign_id={}".format(campaign.store_id, campaign.id))

        leads = AppendedVisitor.query.from_statement(stmt).all()
        campaign_pixelhash = hashlib.sha1(str(campaign.id).encode('utf-8')).hexdigest()
        visitor_count = len(visitors)
        lead_count = len(leads)
        open_count = 0

    return render_template(
        'campaign_detail.html',
        campaign=campaign,
        visitors=visitors[0:100],
        leads=leads,
        today=today,
        form=form,
        approval_form=approval_form,
        creative_form=creative_form,
        store=store,
        campaign_pixelhash=campaign_pixelhash.strip()[-10:],
        pt=pt,
        visitor_count=visitor_count,
        lead_count=lead_count,
        open_count=open_count
    )


@app.route('/campaign/add', methods=['GET', 'POST'])
@login_required
def campaign_add():
    """
    Add new campaign from web form
    :return: new campaign
    """
    form = AddCampaignForm(request.form)

    stores = Store.query.order_by(Store.name.asc()).filter_by(status='Active').all()
    campaign_types = CampaignType.query.order_by(CampaignType.name.asc()).all()

    if request.method == 'POST' and form.validate_on_submit():

        # save the campaign
        campaign = Campaign(
            store_id=form.store_id.data,
            name=form.name.data,
            job_number=form.job_number.data,
            created_date=datetime.datetime.now(),
            created_by=current_user.get_id(),
            type=form.campaign_type.data,
            status=form.status.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            radius=form.radius.data,
            client_id=form.client_id.data,
            pixeltrackers_id=1
        )

        # add the new data object and commit
        db_session.add(campaign)
        db_session.commit()

        # flash success message
        flash('Campaign {} created successfully...'.format(campaign.name), category='success')

        # redirect
        return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id))

    return render_template(
        'campaign_add.html',
        form=form,
        stores=stores,
        campaign_types=campaign_types
    )


@app.route('/create/pixel/<int:campaign_pk_id>', methods=['GET'])
def create_pixel(campaign_pk_id):
    """
    Create Tracking Pixel
    :param campaign_pk_id:
    :return: URL
    """

    # get our list of active trackers
    tracker = PixelTracker.query.filter(
        PixelTracker.active == 1
    ).one()

    # get the campaign instance
    campaign = Campaign.query.get(campaign_pk_id)

    if campaign:
        if tracker:

            # assign the tracker to this campaign
            campaign.pixeltrackers_id == tracker.id
            campaign.status = 'ACTIVE'
            db_session.commit()

            # flash a success message
            flash('The Campaign Pixel Tracker was assigned to {}.'.format(tracker.name), category='success')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id))

        else:
            # can not assign a tracker.  set the campaign status to inactive
            campaign.status = 'INACTIVE'
            db_session.commit()
            flash('Sorry, there are no available Pixel Trackers to assign to this campaign.', category='danger')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id))

    else:

        # flash campaign not found
        flash('Sorry, campaign {} was not found.'.format(campaign_pk_id), category='warning')
        return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id))


@app.route('/admin', methods=['GET'])
def admin_menu():
    pass


@app.route('/leads', methods=['GET'])
@login_required
def leads():
    return render_template(
        'leads.html'
    )


@app.route('/reports', methods=['GET'])
@login_required
def reports():

    form = ReportFilterForm()
    stores = Store.query.order_by('name').filter_by(status='ACTIVE').all()
    campaigns = Campaign.query.order_by(Campaign.name.asc()).filter_by(status='ACTIVE').all()

    return render_template(
        'reports.html',
        today=today,
        form=form,
        campaigns=campaigns,
        stores=stores
    )


@app.route("/login", methods=['GET', 'POST'])
def login():

    if request.method == 'GET':
        return render_template('login.html')

    username = request.form['username']
    password = request.form['password']

    user = User.query.filter_by(username=username).first()

    if user:

        if user.check_password(password):
            login_user(user)
            flash('You have been logged in successfully...', 'success')
            return redirect(request.args.get('next') or url_for('index'))

    flash('Username or password is invalid!  Please try again...')
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    pass


@app.route('/logout', methods=['GET'])
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.errorhandler(404)
def page_not_found(err):
    return render_template('error-404.html'), 404


@app.errorhandler(500)
def internal_server_error(err):
    return render_template('error-500.html'), 500


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


@app.template_filter('datemdy')
def format_date(value):
    dt = value
    return dt.strftime('%m/%d/%Y')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EARL Web Frontend')
    parser.add_argument('command', nargs=1, choices=('run',))
    args = parser.parse_args()
    port = 5580

    app.run(
        debug=debug,
        port=port
    )
