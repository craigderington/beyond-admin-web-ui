from flask import Flask, make_response, redirect, request, Response, render_template, url_for, flash, g
from flask_sslify import SSLify
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy, Pagination
from sqlalchemy import text, and_, exc, func
from database import db_session
from models import User, Store, Campaign, CampaignType, Visitor, AppendedVisitor, Lead, PixelTracker, Contact
from forms import AddCampaignForm, UserLoginForm, AddStoreForm, ApproveCampaignForm, CampaignCreativeForm, \
    ReportFilterForm, ContactForm, UserProfileForm, ChangeUserPasswordForm
import config
import datetime
import hashlib
import pymongo


# debug
debug = False

# app settings
app = Flask(__name__)
sslify = SSLify(app)

# app config
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
login_manager.login_view = "/login"

# disable strict slashes
app.url_map.strict_slashes = False


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

    if request.method == 'POST':

        if 'edit-store-form' in request.form.keys() and form.validate_on_submit():

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
            store.system_notifications = form.system_notifications.data
            store.reporting_email = form.reporting_email.data
            store.simplifi_client_id = form.simplifi_client_id.data
            store.simplifi_company_id = form.simplifi_company_id.data
            store.simplifi_name = form.simplifi_name.data

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
        campaigns=campaigns,
        contacts=contacts,
        campaign_count=campaign_count,
        today=get_date(),
        form=form,
        contact_form=contact_form,
        contact_count=contact_count
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
            reporting_email=form.reporting_email.data,
            system_notifications=form.system_notifications.data
        )

        # commit to the database
        db_session.add(new_store)
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


@app.route('/campaigns', methods=['GET'])
@login_required
def campaigns():
    """
    Get a list of active campaigns
    :return: campaign list
    """
    campaign_count = 0

    campaigns = db_session.query(Campaign).order_by(
        Campaign.created_date.desc()
    ).limit(100).all()

    campaign_types = db_session.query(CampaignType).order_by(
        CampaignType.name.asc()
    ).all()

    if campaigns:
        campaign_count = len(campaigns)

    return render_template(
        'campaigns.html',
        campaigns=campaigns,
        campaign_types=campaign_types,
        campaign_count=campaign_count,
        today=get_date()
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
    leads = None
    visitors = None
    campaign_pixelhash = None
    visitor_count = 0
    lead_count = 0
    open_count = 0
    pt = None
    store = None

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

            # commit to the database
            db_session.commit()

            # flash message and redirect
            flash('Campaign {} Approval was updated successfully'.format(campaign.name), category='info')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id))

        elif 'save-campaign-creative' in request.form.keys() and creative_form.validate_on_submit():
            campaign.creative_header = creative_form.creative_header.data
            campaign.creative_footer = creative_form.creative_footer.data
            campaign.email_subject = creative_form.email_subject.data
            db_session.commit()

            # flash a success message and redirect
            flash('Campaign {} Creative was saved successfully'.format(campaign.name), category='info')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign.id))

    if campaign:

        visitors = db_session.query(Visitor).filter(and_(
            Visitor.job_number == campaign.job_number,
            Visitor.campaign_id == campaign.id
        )).all()

        store = db_session.query(Store).filter(
            Store.id == campaign.store_id
        ).one()

        if campaign.pixeltrackers_id:
            pt = db_session.query(PixelTracker).get(campaign.pixeltrackers_id)

        stmt = text("SELECT v.id, av.* from visitors v, appendedvisitors av where v.id = av.visitor "
                    "and v.store_id={} and v.campaign_id={}".format(campaign.store_id, campaign.id))

        leads = db_session.query(AppendedVisitor).from_statement(stmt).all()
        campaign_pixelhash = hashlib.sha1(str(campaign.id).encode('utf-8')).hexdigest()
        visitor_count = len(visitors)
        lead_count = len(leads)
        open_count = 0

    return render_template(
        'campaign_detail.html',
        campaign=campaign,
        visitors=visitors[0:100],
        leads=leads,
        today=get_date(),
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
            creative_footer='Enter Footer'
        )

        # commit to the database
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
            db_session.commit()

            # flash a success message and redirect
            flash('The Campaign Pixel Tracker was assigned to {}.'.format(tracker.name), category='success')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id))

        else:
            # can not assign a tracker.  set the campaign status to inactive and redirect
            campaign.status = 'INACTIVE'
            db_session.commit()
            flash('Sorry, there are no available Pixel Trackers to assign to this campaign.', category='danger')
            return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id))

    else:

        # flash campaign not found and redirect
        flash('Sorry, campaign {} was not found.'.format(campaign_pk_id), category='warning')
        return redirect(url_for('campaign_detail', campaign_pk_id=campaign_pk_id))


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


@app.route('/reports', methods=['GET'])
@login_required
def reports():

    form = ReportFilterForm()
    stores = db_session.query(Store).order_by('name').filter_by(status='ACTIVE').all()
    campaigns = db_session.query(Campaign).order_by(Campaign.name.asc()).filter_by(status='ACTIVE').all()

    return render_template(
        'reports.html',
        today=get_date(),
        form=form,
        campaigns=campaigns,
        stores=stores
    )


@app.route("/login", methods=['GET', 'POST'])
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


def get_dashboard():
    """
    Get the dashboard data
    :return: dict
    """

    dashboard = {}
    stores = db_session.query(Store).count()
    campaigns = db_session.query(Campaign).count()
    active_stores = db_session.query(Store).filter_by(status='ACTIVE').count()
    active_campaigns = db_session.query(Campaign).filter_by(status='ACTIVE').count()

    dashboard['stores'] = stores
    dashboard['campaigns'] = campaigns
    dashboard['active_stores'] = active_stores
    dashboard['active_campaigns'] = active_campaigns

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
