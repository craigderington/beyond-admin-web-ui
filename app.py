from flask import Flask, make_response, redirect, request, Response, render_template, url_for, flash, g
from flask_mail import Mail, Message
from flask_sslify import SSLify
from flask_session import Session
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy, Pagination
from sqlalchemy import text, and_, exc, func
from database import db_session
from celery import Celery
from models import User, Store, Campaign, CampaignType, Visitor, AppendedVisitor, Lead, PixelTracker, Contact, \
    GlobalDashboard, StoreDashboard, CampaignDashboard
from forms import AddCampaignForm, UserLoginForm, AddStoreForm, ApproveCampaignForm, CampaignCreativeForm, \
    ReportFilterForm, ContactForm, UserProfileForm, ChangeUserPasswordForm, RVMForm, CampaignStoreFilterForm
import config
import random
import datetime
import hashlib
import pymongo
import phonenumbers
import time
import redis


# debug
debug = False

# app config
app = Flask(__name__)
sslify = SSLify(app)
app.secret_key = config.SECRET_KEY

# session persistence
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('172.26.7.220:6379')
app.config['SESSION_PERMANENT'] = True
sess = Session()
sess.init_app(app)

# mongo config
app.config['MONGO_SERVER'] = config.MONGO_SERVER
app.config['MONGO_DB'] = config.MONGO_DB

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.mailgun.org'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = config.MAIL_DEFAULT_SENDER

# SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS
db = SQLAlchemy(app)

# Mongo DB
mongo_client = pymongo.MongoClient(app.config['MONGO_SERVER'], 27017, connect=False)
mongo_db = mongo_client[app.config['MONGO_DB']]

# define our login_manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/auth/login"
login_manager.login_message = "Login required to access this site."
login_manager.login_message_category = "primary"

# disable strict slashes
app.url_map.strict_slashes = False

# Celery config
app.config['CELERY_BROKER_URL'] = config.CELERY_BROKER_URL
app.config['CELERY_RESULT_BACKEND'] = config.CELERY_RESULT_BACKEND
app.config['CELERY_ACCEPT_CONTENT'] = config.CELERY_ACCEPT_CONTENT
app.config.update(accept_content=['json', 'pickle'])

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Config mail
mail = Mail(app)


# clear all db sessions at the end of each request
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


# load the user
@login_manager.user_loader
def load_user(id):
    try:
        return db_session.query(User).get(int(id))
    except exc.SQLAlchemyError as err:
        return None


# run before each request
@app.before_request
def before_request():
    g.user = current_user


# tasks sections, for async functions, etc...
@celery.task(serializer='pickle')
def send_async_email(msg):
    """Background task to send an email with Flask-Mail."""
    with app.app_context():
        mail.send(msg)


@celery.task(bind=True)
def long_task(self):
    """Background task that runs a long function with progress reports."""
    verb = ['Starting up', 'Booting', 'Repairing', 'Loading', 'Checking']
    adjective = ['master', 'radiant', 'silent', 'harmonic', 'fast']
    noun = ['solar array', 'particle reshaper', 'cosmic ray', 'orbiter', 'bit']
    message = ''
    total = random.randint(10, 50)
    for i in range(total):
        if not message or random.random() < 0.25:
            message = '{0} {1} {2}...'.format(random.choice(verb),
                                              random.choice(adjective),
                                              random.choice(noun))
        self.update_state(state='PROGRESS',
                          meta={'current': i, 'total': total,
                                'status': message})
        time.sleep(1)
    return {'current': 100, 'total': 100, 'status': 'Task completed!',
            'result': 42}


# default routes
@app.route('/', methods=['GET'])
@app.route('/index', methods=['GET'])
@login_required
def index():
    """
    The default view.   Dashboard
    :return: databoxes
    """

    return render_template(
        'index.html',
        current_user=current_user,
        dashboard=get_dashboard(),
        campaign_types=get_campaign_types(),
        today=get_date()
    )


@app.route('/dashboard/history', methods=['GET'])
def dashboard_history():
    """
    Show the dashboard historical data
    :return: queryset
    """
    dashboards = None
    dashboard_count = 0

    try:
        dashboards = db_session.query(GlobalDashboard).order_by(GlobalDashboard.id.desc()).limit(100)
        dashboard_count = dashboards.count()

    except exc.SQLAlchemyError as err:
        flash('The dashboard history view returned a database error: {}'.format(str(err)), category='danger')
        return redirect(url_for('index'))

    return render_template(
        'dashboard_history.html',
        today=get_date(),
        dashboards=dashboards,
        dashboard_count=dashboard_count
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

    stores = db_session.query(Store).filter(
        Store.status == 'Active'
    ).all()

    if stores:
        store_count = len(stores)

    return render_template(
        'stores.html',
        stores=stores,
        store_count=store_count,
        today=get_date()
    )


@app.route('/store/<int:store_pk_id>', methods=['GET', 'POST'])
def store_detail(store_pk_id):
    """
    Get the store details by Store ID
    :param store_pk_id:
    :return: store obj
    """

    store = db_session.query(Store).filter(
        Store.id == store_pk_id
    ).one()

    campaigns = db_session.query(Campaign).order_by(
        Campaign.created_date.desc()
    ).filter(
        Campaign.store_id == store_pk_id
    ).limit(100).all()

    contacts = db_session.query(Contact).order_by(
        Contact.last_name.asc()
    ).filter(
        Contact.store_id == store.id
    ).all()

    campaign_count = len(campaigns)
    contact_count = len(contacts)
    form = AddStoreForm(request.form)
    contact_form = ContactForm(request.form)
    storephonenumber = phonenumbers.parse(store.phone_number, 'US')
    store_phone = phonenumbers.format_number(storephonenumber, phonenumbers.PhoneNumberFormat.NATIONAL)
    dashboard = db_session.query(StoreDashboard).filter(
        StoreDashboard.store_id == store.id
    ).order_by(StoreDashboard.id.desc()).limit(1).one()

    if request.method == 'POST':

        if 'edit-store-form' in request.form.keys() and form.validate_on_submit():

            phone_number = form.phone_number.data
            parsed_number = phonenumbers.parse(phone_number, 'US')

            # update our instance of store
            store.client_id = form.client_id.data
            store.status = form.status.data
            store.name = form.name.data
            store.address1 = form.address1.data
            store.address2 = form.address2.data
            store.city = form.city.data
            store.state = form.state.data.upper()
            store.zip_code = form.zip_code.data
            store.phone_number = parsed_number.national_number,
            store.adf_email = form.adf_email.data
            store.notification_email = form.notification_email.data
            store.system_notifications = form.system_notifications.data
            store.reporting_email = form.reporting_email.data
            store.simplifi_client_id = form.simplifi_client_id.data
            store.system_notifications=form.system_notifications.data

            # commit to the database
            db_session.commit()

            # flash a message and redirect
            flash('The store details were saved successfully...', category='success')
            return redirect(url_for('store_detail', store_pk_id=store.id))

        elif 'add-new-contact' in request.form.keys() and contact_form.validate_on_submit():

            # add the store contact
            new_contact = Contact(
                store_id=store.id,
                first_name=contact_form.first_name.data,
                last_name=contact_form.last_name.data,
                title=contact_form.title.data,
                email=contact_form.email.data,
                mobile=contact_form.mobile.data
            )

            # commit to the database
            db_session.add(new_contact)
            db_session.commit()

            # flash a message and redirect
            flash('New Contact {} {} was successfully added...'.format(new_contact.first_name, new_contact.last_name),
                  category='success')
            return redirect(url_for('store_detail', store_pk_id=store.id) + '#contacts')

    return render_template(
        'store_detail.html',
        store=store,
        store_phone=store_phone,
        campaigns=campaigns,
        contacts=contacts,
        campaign_count=campaign_count,
        today=get_date(),
        form=form,
        contact_form=contact_form,
        contact_count=contact_count,
        dashboard=dashboard
    )


@app.route('/store/add', methods=['GET', 'POST'])
def store_add():
    """
    Create a new store from the web data form
    :return: store ID
    """

    form = AddStoreForm(request.form)
    
    if request.method == 'POST' and form.validate_on_submit():

        # clean the phone number field
        phone_number = form.phone_number.data
        parsed_number = phonenumbers.parse(phone_number, 'US')

        new_store = Store(
            client_id=form.client_id.data,
            name=form.name.data,
            address1=form.address1.data,
            address2=form.address2.data,
            city=form.city.data,
            state=form.state.data.upper(),
            zip_code=form.zip_code.data,
            status=form.status.data,
            phone_number=parsed_number.national_number,
            notification_email=form.notification_email.data,
            reporting_email=form.reporting_email.data,
            system_notifications=form.system_notifications.data
        )

        # commit to the database
        db_session.add(new_store)
        db_session.commit()
        db_session.flush()

        # set the new vars
        store_id = new_store.id

        # create a dashboard object so we don't break the
        # store detail view
        dashboard = StoreDashboard(
            store_id=store_id,
            total_campaigns=0,
            active_campaigns=0,
            total_global_visitors=0,
            total_unique_visitors=0,
            total_us_visitors=0,
            total_appends=0,
            total_sent_to_dealer=0,
            total_sent_followup_emails=0,
            total_rvms_sent=0,
            global_append_rate=0.00,
            unique_append_rate=0.00,
            us_append_rate=0.00
        )

        # save our new dashboard object
        db_session.add(dashboard)
        db_session.commit()

        # flash message and redirect to store detail
        flash('Store: {}, ID: {} was created successfully... '
              'Edit the store details here.'.format(new_store.id, new_store.name),
              category='success')
        return redirect(url_for('store_detail', store_pk_id=new_store.id))

    return render_template(
        'store_add.html',
        form=form,
        today=get_date()
    )


@app.route('/campaigns', methods=['GET', 'POST'])
@login_required
def campaigns():
    """
    Get a list of active campaigns
    :return: store campaign list
    """

    form = CampaignStoreFilterForm()
    campaigns = []
    campaign_count = 0

    store_filter = db_session.query(Store).filter(
        Store.status == 'ACTIVE'
    ).order_by(Store.name.asc()).all()

    if request.method == 'POST' and form.validate_on_submit():
        store_id = form.store_id.data

        campaigns = db_session.query(Campaign).filter(
            Campaign.store_id == store_id
        ).order_by(
            Campaign.created_date.desc()
        ).limit(50).all()

    if campaigns:
        campaign_count = len(campaigns)

    return render_template(
        'campaigns.html',
        stores=store_filter,
        campaigns=campaigns,
        campaign_count=campaign_count,
        today=get_date(),
        form=form
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
    rvm_form = RVMForm()
    leads = None
    visitors = None
    campaign_pixelhash = None
    visitor_count = 0
    lead_count = 0
    open_count = 0
    pt = None
    store = None
    dashboard = None

    # first, get our campaign
    campaign = db_session.query(Campaign).filter(
        Campaign.id == campaign_pk_id
    ).one()

    if request.method == 'POST':

        if 'save-campaign-settings' in request.form.keys() and form.validate_on_submit():

            # update the campaign data
            campaign.job_number = form.job_number.data
            campaign.client_id = form.client_id.data
            campaign.radius = form.radius.data
            campaign.start_date = form.start_date.data
            campaign.end_date = form.end_date.data
            campaign.name = form.name.data
            campaign.status = form.status.data
            campaign.adf_subject = form.adf_subject.data

            # commit to the database
            db_session.commit()

            flash('Campaign {} Settings were updated successfully'.format(campaign.name), category='success')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id) + '?=settings')

        elif 'save-campaign-approval' in request.form.keys() and approval_form.validate_on_submit():

            # update the campaign data
            campaign.options = approval_form.options.data
            campaign.description = approval_form.description.data
            campaign.funded = approval_form.funded.data
            campaign.approved = approval_form.approved.data
            if campaign.approved:
                campaign.approved_by = current_user.get_id()
            campaign.objective = approval_form.objective.data
            campaign.frequency = approval_form.frequency.data

            # commit to the database
            db_session.commit()

            # flash message and redirect
            flash('Campaign {} Approval was updated successfully'.format(campaign.name), category='success')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id) + '?=approval')

        elif 'save-campaign-creative' in request.form.keys() and creative_form.validate_on_submit():

            # update the campaign creative
            campaign.creative_header = creative_form.creative_header.data
            campaign.creative_footer = creative_form.creative_footer.data
            campaign.email_subject = creative_form.email_subject.data

            # commit to the database
            db_session.commit()

            # flash a success message and redirect
            flash('Campaign {} Creative was saved successfully'.format(campaign.name), category='success')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id) + '?=creative')

        elif 'save-campaign-rvm' in request.form.keys() and rvm_form.validate_on_submit():

            # update the campaign rvm settings
            campaign.rvm_campaign_id = rvm_form.rvm_campaign_id.data
            campaign.rvm_limit = rvm_form.rvm_limit.data

            # commit to the database
            db_session.commit()

            # flash a message and redirect
            flash('Campaign {} RVM settings were successfully updated...'.format(campaign.name), category='success')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id) + '?=rvm')

    if campaign:

        store = db_session.query(Store).filter(
            Store.id == campaign.store_id
        ).one()

        if campaign.pixeltrackers_id:
            pt = db_session.query(PixelTracker).get(campaign.pixeltrackers_id)

        campaign_pixelhash = hashlib.sha1(str(campaign.id).encode('utf-8')).hexdigest()

        try:
            # get the campaign dashboard
            dashboard = db_session.query(CampaignDashboard).filter(
                CampaignDashboard.campaign_id == campaign.id
            ).order_by(CampaignDashboard.id.desc()).limit(1).one()

        except exc.SQLAlchemyError as err:
            flash('Database returned error: {}'.format(str(err)), category='danger')
            return redirect(url_for('index'))

    return render_template(
        'campaign_detail.html',
        campaign=campaign,
        today=get_date(),
        form=form,
        approval_form=approval_form,
        creative_form=creative_form,
        rvm_form=rvm_form,
        store=store,
        campaign_pixelhash=campaign_pixelhash.strip()[-10:],
        pt=pt,
        dashboard=dashboard
    )


@app.route('/campaign/add', methods=['GET', 'POST'])
@login_required
def campaign_add():
    """
    Add new campaign from web form
    :return: new campaign
    """
    form = AddCampaignForm(request.form)
    stores = db_session.query(Store).order_by(Store.name.asc()).filter_by(status='Active').all()
    campaign_types = db_session.query(CampaignType).order_by(CampaignType.name.asc()).all()
    store_id = request.args.get('store_id')
    client_id = request.args.get('client_id')

    if store_id:
        store_id = int(store_id)

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
            approved=0,
            funded=0,
            creative_header='Enter Header',
            creative_footer='Enter Footer',
            pixeltrackers_id=1
        )

        # commit to the database
        db_session.add(campaign)
        db_session.commit()
        db_session.flush()

        # set the variables of the newly inserted campaign ID and store ID
        campaign_id = campaign.id
        store_id = campaign.store_id

        # create a dashboard object so we don't break
        # the campaign detail page
        dashboard = CampaignDashboard(
            store_id=store_id,
            campaign_id=campaign_id
        )

        db_session.add(dashboard)
        db_session.commit()

        # flash success message
        flash('Campaign {} created successfully...'.format(campaign.name), category='success')

        # redirect
        return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id))

    return render_template(
        'campaign_add.html',
        form=form,
        stores=stores,
        store_id=store_id,
        client_id=client_id,
        campaign_types=campaign_types,
        today=get_date()
    )


@app.route('/create/pixel/<int:campaign_pk_id>', methods=['GET'])
def create_pixel(campaign_pk_id):
    """
    Create Tracking Pixel
    :param campaign_pk_id:
    :return: URL
    """

    # get our list of active trackers
    tracker = db_session.query(PixelTracker).filter(
        PixelTracker.active == 1
    ).one()

    # get the campaign instance
    campaign = db_session.query(Campaign).get(campaign_pk_id)

    if campaign:
        if tracker:

            # assign the tracker to this campaign
            campaign.pixeltrackers_id == tracker.id
            campaign.status = 'ACTIVE'

            # commit to the database
            db_session.commit()

            # flash a success message and redirect
            flash('The Campaign Pixel Tracker was assigned to {}.'.format(tracker.name), category='success')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id) + '?=tracker')

        else:
            # can not assign a tracker.  set the campaign status to inactive and redirect
            campaign.status = 'INACTIVE'
            db_session.commit()
            flash('Sorry, there are no available Pixel Trackers to assign to this campaign.', category='danger')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id) + '?=tracker')

    else:

        # flash campaign not found and redirect
        flash('Sorry, campaign {} was not found.'.format(campaign_pk_id), category='warning')
        return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id) + '?=tracker')


@app.route('/admin', methods=['GET'])
@login_required
def admin():
    """
    Administrative Menu
    :return: html page
    """
    return render_template(
        'admin.html',
        today=get_date()
    )


@app.route('/leads', methods=['GET'])
@login_required
def leads():
    return render_template(
        'leads.html'
    )


@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():

    form = ReportFilterForm()
    stores = db_session.query(Store).order_by('name').filter_by(status='ACTIVE').all()
    store_id = None
    store_name = None
    results = None
    results_list = []
    results_count = 0
    campaign_id = None
    current_time = datetime.datetime.now()
    ct_date_string = current_time.strftime('%Y-%m-%d')
    yesterday = (current_time - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    start_date = datetime.datetime.strptime(yesterday + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
    end_date = datetime.datetime.strptime(yesterday + ' 23:59:59', '%Y-%m-%d %H:%M:%S')

    if request.method == 'POST' and form.validate_on_submit():

        if 'get-store-campaigns' in request.form.keys():
            if 'report_date_range' in request.form.keys():
                campaign_dates = form.report_date_range.data.split('-')
                r1_date = datetime.datetime.strptime(campaign_dates[0].strip(), '%m/%d/%Y')
                r2_date = datetime.datetime.strptime(campaign_dates[1].strip(), '%m/%d/%Y')
                s_date = r1_date.strftime('%Y-%m-%d')
                e_date = r2_date.strftime('%Y-%m-%d')
                start_date = datetime.datetime.strptime(s_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
                end_date = datetime.datetime.strptime(e_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S')

            # set the store details and ID
            store_id = form.store_id.data
            store = db_session.query(Store).filter(
                Store.id == store_id
            ).one()
            store_name = store.name

            # get the store active campaigns
            campaign_list = db_session.query(Campaign).filter(
                Campaign.store_id == store_id,
                Campaign.status == 'ACTIVE'
            ).all()

            if campaign_list:

                for campaign in campaign_list:

                    # raw sql report query
                    stmt = text("select c.job_number, c.id, c.name, ct.name as campaign_type, "
                                "(select sum(v1.num_visits) from visitors v1 where v1.campaign_id = c.id and v1.created_date between '{}' and '{}') as total_visitors, "
                                "(select count(v1.id) from visitors v1 where v1.campaign_id = c.id and v1.created_date between '{}' and '{}') as total_unique_visitors, "
                                "(select count(av1.id) from appendedvisitors av1, visitors v2 where av1.visitor = v2.id and v2.campaign_id = c.id and v2.created_date between '{}' and '{}') as total_appends, "
                                "(select count(l2.id) from leads l2, appendedvisitors av3, visitors v3 where l2.appended_visitor_id = av3.id and av3.visitor = v3.id and v3.campaign_id = c.id and v3.created_date between '{}' and '{}') as total_leads, "
                                "(select count(l2.id) from leads l2, appendedvisitors av3, visitors v3 where l2.appended_visitor_id = av3.id and av3.visitor = v3.id and v3.campaign_id = c.id and v3.created_date between '{}' and '{}' and l2.sent_to_dealer = 1) as total_sent_to_dealer, "
                                "(select count(l2.id) from leads l2, appendedvisitors av3, visitors v3 where l2.appended_visitor_id = av3.id and av3.visitor = v3.id and v3.campaign_id = c.id and v3.created_date between '{}' and '{}' and l2.sent_adf = 1) as total_adfs, "
                                "(select count(l2.id) from leads l2, appendedvisitors av3, visitors v3 where l2.appended_visitor_id = av3.id and av3.visitor = v3.id and v3.campaign_id = c.id and v3.created_date between '{}' and '{}' and l2.followup_email = 1) as total_followup_emails, "
                                "(select count(l2.id) from leads l2, appendedvisitors av3, visitors v3 where l2.appended_visitor_id = av3.id and av3.visitor = v3.id and v3.campaign_id = c.id and v3.created_date between '{}' and '{}' and l2.rvm_sent = 1) as total_rvms, "
                                "(select count(l2.id) from leads l2, appendedvisitors av3, visitors v3 where l2.appended_visitor_id = av3.id and av3.visitor = v3.id and v3.campaign_id = c.id and v3.created_date between '{}' and '{}' and l2.email_verified = 1) as total_email_verified "
                                "from campaigns c, visitors v, stores s, appendedvisitors av, leads l, campaigntypes ct "
                                "where c.id = v.campaign_id "
                                "and c.store_id = s.id "
                                "and v.id = av.visitor "
                                "and l.appended_visitor_id = av.id "
                                "and s.id = {} "
                                "and c.id = {} "
                                "and c.status = 'ACTIVE' "
                                "and c.type = ct.id "
                                "and (v.created_date between '{}' and '{}') "
                                "GROUP BY c.job_number, c.id, c.name, ct.name "
                                "order by c.job_number asc".format(start_date, end_date, start_date, end_date,
                                                                   start_date, end_date, start_date, end_date,
                                                                   start_date, end_date, start_date, end_date,
                                                                   start_date, end_date, start_date, end_date,
                                                                   start_date, end_date,
                                                                   store_id, campaign.id,
                                                                   start_date, end_date))

                    results = db_session.query('job_number', 'id', 'name', 'campaign_type', 'total_visitors',
                                               'total_unique_visitors', 'total_appends', 'total_leads',
                                               'total_sent_to_dealer', 'total_adfs', 'total_followup_emails',
                                               'total_rvms', 'total_email_verified').from_statement(stmt).all()
                    if results:
                        results_list.append(results)
                        results_count = len(results_list)

    return render_template(
        'reports.html',
        today=get_date(),
        form=form,
        stores=stores,
        store_id=store_id,
        store_name=store_name,
        results_list=results_list,
        start_date=start_date,
        end_date=end_date,
        campaign_id=campaign_id,
        results_count=results_count
    )


@app.route('/login', methods=['GET'])
def login_redirect():
    """
    Redirect to auth/login
    :return: redirect url
    """
    return redirect(url_for('login'), 302)


@app.route("/auth/login", methods=['GET', 'POST'])
def login():

    form = UserLoginForm()

    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = db_session.query(User).filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash('Username or password is invalid!  Please try again...')
            return redirect(url_for('login'))

        # login the user and redirect
        login_user(user)
        flash('You have been logged in successfully...', 'success')
        return redirect(request.args.get('next') or url_for('index'))

    return render_template(
        'login.html',
        form=form
    )


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """
    Allow user to edit their personal profile
    :return: user
    """
    # set the user instance
    user = db_session.query(User).get(current_user.get_id())
    form = UserProfileForm(request.form)
    change_password_form = ChangeUserPasswordForm(request.form)

    if request.method == 'POST':

        if 'save-profile-form' in request.form.keys() and form.validate_on_submit():
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data
            user.email = form.email.data

            # commit to the database
            db_session.commit()

            # flash a message and redirect
            flash('Your user profile has been successfully updated...', category='success')
            return redirect(url_for('profile'))

        elif 'change-password-form' in request.form.keys() and change_password_form.validate_on_submit():

            if user:

                # check the existing password
                if user.check_password(form.current_password.data):

                    # save the new password
                    user.password = user.set_password(form.password.data)

                    # commit to the database
                    db_session.commit()

                    # flash a message and redirect
                    flash('Your password was successfully changed...  Please make a note of this change.', category='info')
                    return redirect(url_for('profile'))

                else:

                    # flash a message that the password is wrong or does not match
                    flash('Sorry, the password does not match; incorrect password...', category='danger')
                    return redirect(url_for('profile'))

    return render_template(
        'profile.html',
        user=user,
        today=get_date(),
        form=form,
        change_password_form=change_password_form
    )


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


def send_email(to, subject, msg_body, **kwargs):
    """
    Send Mail function
    :param to:
    :param subject:
    :param template:
    :param kwargs:
    :return: celery async task id
    """
    msg = Message(
        subject,
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=[to, ]
    )
    msg.body = "EARL Dealer Demo UI Test"
    msg.html = msg_body
    send_async_email.delay(msg)


@app.route('/campaign/<int:campaign_pk_id>/creative/test', methods=['GET'])
def send_test_creative(campaign_pk_id, **kwargs):
    """
    Send Test Creative Mail function
    :param campaign_pk_id
    :param kwargs:
    :return: celery async task id
    """

    try:
        campaign = db_session.query(Campaign).filter(
            Campaign.id == campaign_pk_id
        ).one()

        # check to see if we have a valid campaign
        if campaign:
            subject = 'TEST TEST TEST ' + campaign.email_subject
            recipients = "earl-validation-email@contactdms.com"
            msg_body = campaign.creative_header + ' TEST CLIENT NAME ' + campaign.creative_footer

            # create the message
            msg = Message(
                subject,
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[recipients, ]
            )

            # modify the message obj
            msg.body = ""
            msg.add_recipient("rank@contactdms.com")
            msg.html = msg_body

            # send message async, pass to Celery queue
            send_async_email.delay(msg)

            # flash a message and show result
            flash('Campaign {} {} test creative email was sent successfully.  '
                  'Test email sent to: {}'.format(campaign.name, campaign.id, recipients), category='success')

            # redirect back to creative page
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id) + '?=creative')

    except exc.SQLAlchemyError as err:
        # flash an error message
        flash('Database returned error: {}'.format(str(err)), category='danger')
        return redirect(url_for('index'))


def get_dashboard():
    """
    Get the dashboard data
    :return: dict
    """
    dashboard = {}
    dashboard = db_session.query(GlobalDashboard).order_by(GlobalDashboard.id.desc()).limit(1).one()
    return dashboard


def get_campaign_types():
    """
    Get a list of campaign types
    :return: query object
    """

    stmt = text("SELECT DISTINCT(ct.name), count(*) as ctcount "
                "FROM campaigntypes ct, campaigns c "
                "WHERE ct.id = c.type "
                "GROUP BY ct.name "
                "ORDER BY ct.name ASC")

    campaign_types = db_session.query('name', 'ctcount').from_statement(stmt).all()
    return campaign_types


def get_date():
    # set the current date time for each page
    today = datetime.datetime.now().strftime('%c')
    return '{}'.format(today)


@app.template_filter('formatdate')
def format_date(value):
    dt = value
    return dt.strftime('%Y-%m-%d %H:%M')


@app.template_filter('datemdy')
def format_date(value):
    dt = value
    return dt.strftime('%m/%d/%Y')


@app.template_filter('formatphonenumber')
def format_phone_number(value):
    phone_number = value.replace('(-)', '')
    return '{}-{}-{}'.format(phone_number[:3], phone_number[3:6], phone_number[6:])


if __name__ == '__main__':

    port = 5580

    # start the application
    app.run(
        debug=debug,
        port=port
    )
