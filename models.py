from database import Base
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Float
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
# Define application Bases


class User(Base):
    __tablename__ = 'ab_user'
    id = Column(Integer, primary_key=True)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=False)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password = Column(String(256), nullable=False)
    active = Column(Boolean, default=1)
    email = Column(String(120), unique=True, nullable=False)
    last_login = Column(DateTime)
    login_count = Column(Integer)
    fail_login_count = Column(Integer)
    created_on = Column(DateTime, default=datetime.now, nullable=True)
    changed_on = Column(DateTime, default=datetime.now, nullable=True)
    created_by_fk = Column(Integer)
    changed_by_fk = Column(Integer)

    def __init__(self, username, password):
        self.username = username
        self.set_password(password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return int(self.id)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        if self.last_name and self.first_name:
            return '{} {}'.format(
                self.first_name,
                self.last_name
            )


class Visitor(Base):
    __tablename__ = 'visitors'
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    store_id = Column(Integer, ForeignKey('stores.id'))
    created_date = Column(DateTime, onupdate=datetime.now)
    ip = Column(String(15), index=True)
    user_agent = Column(String(255))
    job_number = Column(Integer)
    client_id = Column(String(255))
    appended = Column(Boolean, default=False)
    open_hash = Column(String(255))
    campaign_hash = Column(String(255))
    send_hash = Column(String(255))
    num_visits = Column(Integer)
    last_visit = Column(DateTime)
    raw_data = Column(Text)
    processed = Column(Boolean, default=False)
    campaign = relationship("Campaign")
    store = relationship("Store")
    country_name = Column(String(255))
    city = Column(String(255))
    time_zone = Column(String(50))
    longitude = Column(String(50))
    latitude = Column(String(50))
    metro_code = Column(String(10))
    country_code = Column(String(2))
    country_code3 = Column(String(3))
    dma_code = Column(String(3))
    area_code = Column(String(3))
    postal_code = Column(String(5))
    region = Column(String(50))
    region_name = Column(String(255))
    traffic_type = Column(String(255))
    retry_counter = Column(Integer)
    last_retry = Column(DateTime)
    status = Column(String(10))
    locked = Column(Boolean, default=0)

    def __repr__(self):
        return 'From {} on {} for {}'.format(
            self.ip,
            self.created_date,
            self.campaign
        )

    def get_geoip_data(self):
        return '{} {} {} {} {}'.format(
            self.country_code,
            self.city,
            self.region,
            self.postal_code,
            self.traffic_type
        )


class AppendedVisitor(Base):
    __tablename__ = 'appendedvisitors'
    id = Column(Integer, primary_key=True)
    visitor = Column(Integer, ForeignKey('visitors.id'))
    visitor_relation = relationship("Visitor")
    created_date = Column(DateTime, onupdate=datetime.now)
    first_name = Column(String(255))
    last_name = Column(String(255))
    email = Column(String(255))
    home_phone = Column(String(15))
    cell_phone = Column(String(15))
    address1 = Column(String(255))
    address2 = Column(String(255))
    city = Column(String(255))
    state = Column(String(2))
    zip_code = Column(String(5))
    zip_4 = Column(Integer)
    credit_range = Column(String(50))
    car_year = Column(Integer)
    car_make = Column(String(255))
    car_model = Column(String(255))
    processed = Column(Boolean, default=False)

    def __repr__(self):
        return '{} {}'.format(
            self.first_name,
            self.last_name
        )


class Lead(Base):
    __tablename__ = 'leads'
    id = Column(Integer, primary_key=True)
    appended_visitor_id = Column(Integer, ForeignKey('appendedvisitors.id'), nullable=False)
    appended_visitor = relationship("AppendedVisitor")
    created_date = Column(DateTime, onupdate=datetime.now)
    email_verified = Column(Boolean, default=False)
    lead_optout = Column(Boolean, default=False)
    processed = Column(Boolean, default=False)
    followup_email = Column(Boolean, default=False)
    followup_voicemail = Column(Boolean, default=False)
    followup_print = Column(Boolean, default=False)
    email_receipt_id = Column(String(255))
    sent_to_dealer = Column(Boolean, default=False)
    email_validation_message = Column(String(50))
    sent_adf = Column(Boolean, default=False)
    adf_email_receipt_id = Column(String(255))
    adf_email_validation_message = Column(String(50))
    rvm_status = Column(String(20), nullable=True)
    rvm_date = Column(DateTime)
    rvm_message = Column(String(50))
    rvm_sent = Column(Boolean, default=0, nullable=False)
    followup_email_sent_date = Column(DateTime)
    followup_email_receipt_id = Column(String(255), nullable=True, default='NOID')
    followup_email_status = Column(String(20), nullable=True, default='NOTSENT')
    followup_email_delivered = Column(Boolean, default=False, nullable=True)
    followup_email_bounced = Column(Boolean, default=False, nullable=True)
    followup_email_opens = Column(Integer, default=0, nullable=True)
    followup_email_clicks = Column(Integer, default=0, nullable=True)
    followup_email_spam = Column(Boolean, default=False, nullable=True)
    followup_email_unsub = Column(Boolean, default=False, nullable=True)
    followup_email_dropped = Column(Boolean, default=False, nullable=True)
    dropped_reason = Column(String(50))
    dropped_code = Column(String(50))
    dropped_description = Column(String(255))
    bounce_error = Column(String(255))
    followup_email_click_ip = Column(String(255))
    followup_email_click_device = Column(String(255))
    followup_email_click_campaign = Column(String(255))
    webhook_last_update = Column(DateTime, onupdate=datetime.now, nullable=True)
    followup_email_open_campaign = Column(String(255), nullable=True)
    followup_email_open_ip = Column(String(255), nullable=True)
    followup_email_open_device = Column(String(255), nullable=True)

    def __repr__(self):
        return '{}'.format(
            self.id
        )


class Store(Base):
    __tablename__ = 'stores'
    id = Column(Integer, primary_key=True)
    client_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), unique=True, nullable=False)
    address1 = Column(String(255), nullable=False)
    address2 = Column(String(255))
    city = Column(String(255), nullable=False)
    state = Column(String(2), nullable=False)
    zip_code = Column(String(10), nullable=False)
    zip_4 = Column(String(10))
    status = Column(String(20), default='Active', nullable=False)
    adf_email = Column(String(255))
    notification_email = Column(String(255), nullable=False)
    reporting_email = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)
    simplifi_company_id = Column(Integer)
    simplifi_client_id = Column(String(255))
    simplifi_name = Column(String(255))
    system_notifications = Column(String(255))

    def __repr__(self):
        return '{}'.format(
            self.name
        )

    def get_id(self):
        return int(self.id)


class CampaignType(Base):
    __tablename__ = 'campaigntypes'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)

    def __repr__(self):
        return '{}'.format(
            self.name
        )


class Campaign(Base):
    __tablename__ = 'campaigns'
    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    store = relationship('Store')
    name = Column(String(255), nullable=False)
    job_number = Column(Integer, unique=True, nullable=False)
    created_date = Column(DateTime, onupdate=datetime.now)
    created_by = Column(Integer, ForeignKey('ab_user.id'))
    type = Column(Integer, ForeignKey('campaigntypes.id'), nullable=False)
    campaign_type = relationship('CampaignType')
    options = Column(Text(length=1024))
    description = Column(Text(length=1024))
    funded = Column(Boolean, default=0)
    approved = Column(Boolean, default=0)
    approved_by = Column(Integer, ForeignKey('ab_user.id'))
    status = Column(String(255), nullable=False)
    objective = Column(Text(length=1024))
    frequency = Column(String(255))
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    radius = Column(Integer, default=50, nullable=False)
    pixeltrackers_id = Column(Integer, ForeignKey('pixeltrackers.id'))
    pixeltracker = relationship('PixelTracker')
    client_id = Column(String(20), nullable=False)
    creative_header = Column(Text)
    creative_footer = Column(Text)
    email_subject = Column(String(255))
    adf_subject = Column(String(255))
    rvm_campaign_id = Column(Integer, unique=True, nullable=True, default=0)
    rvm_send_count = Column(Integer, default=0)
    rvm_limit = Column(Integer, nullable=False, default=10000)

    def __repr__(self):
        return '{}'.format(
            self.name
        )


class PixelTracker(Base):
    __tablename__ = 'pixeltrackers'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    ip_addr = Column(String(15), unique=True, nullable=False)
    fqdn = Column(String(255), unique=True, nullable=False)
    capacity = Column(Integer, default=200, nullable=False)
    total_campaigns = Column(Integer)
    active = Column(Boolean, default=1)

    def __repr__(self):
        return '{}'.format(
            self.name
        )


class Contact(Base):
    __tablename__ = 'contacts'
    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey('stores.id'))
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    title = Column(String(50), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    mobile = Column(String(255), unique=True, nullable=False)


class GlobalDashboard(Base):
    __tablename__ = 'dashboard'
    id = Column(Integer, primary_key=True)
    total_stores = Column(Integer, default=0, nullable=False)
    active_stores = Column(Integer, default=0, nullable=False)
    total_campaigns = Column(Integer, default=0, nullable=False)
    active_campaigns = Column(Integer, default=0, nullable=False)
    total_global_visitors = Column(Integer, default=0, nullable=False)
    total_unique_visitors = Column(Integer, default=0, nullable=False)
    total_us_visitors = Column(Integer, default=0, nullable=False)
    total_appends = Column(Integer, default=0, nullable=False)
    total_sent_to_dealer = Column(Integer, default=0, nullable=False)
    total_sent_followup_emails = Column(Integer, default=0, nullable=False)
    total_rvms_sent = Column(Integer, default=0, nullable=False)
    global_append_rate = Column(Float, default=0.00, nullable=False)
    unique_append_rate = Column(Float, default=0.00, nullable=False)
    us_append_rate = Column(Float, default=0.00, nullable=False)
    last_update = Column(DateTime, onupdate=datetime.now, nullable=True)

    def __repr__(self):
        return '{}'.format(self.id)


class StoreDashboard(Base):
    __tablename__ = 'store_dashboard'
    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey('stores.id'))
    store_name = relationship("Store")
    total_campaigns = Column(Integer, default=0, nullable=False)
    active_campaigns = Column(Integer, default=0, nullable=False)
    total_global_visitors = Column(Integer, default=0, nullable=False)
    total_unique_visitors = Column(Integer, default=0, nullable=False)
    total_us_visitors = Column(Integer, default=0, nullable=False)
    total_appends = Column(Integer, default=0, nullable=False)
    total_sent_to_dealer = Column(Integer, default=0, nullable=False)
    total_sent_followup_emails = Column(Integer, default=0, nullable=False)
    total_rvms_sent = Column(Integer, default=0, nullable=False)
    global_append_rate = Column(Float, default=0.00, nullable=False)
    unique_append_rate = Column(Float, default=0.00, nullable=False)
    us_append_rate = Column(Float, default=0.00, nullable=False)
    last_update = Column(DateTime, onupdate=datetime.now, nullable=True)

    def __repr__(self):
        return '{}'.format(self.id)


class CampaignDashboard(Base):
    __tablename__ = 'campaign_dashboard'
    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    store_name = relationship("Store")
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    campaign_name = relationship("Campaign")
    total_visitors = Column(Integer, default=0, nullable=True)
    total_appends = Column(Integer, default=0, nullable=True)
    total_rtns = Column(Integer, default=0, nullable=True)
    total_followup_emails = Column(Integer, default=0, nullable=True)
    total_rvms = Column(Integer, default=0, nullable=True)
    append_rate = Column(Float, default=0.00, nullable=True)
    last_update = Column(DateTime, onupdate=datetime.now, nullable=True)

    def __repr__(self):
        return '{} {} {}'.format(
            self.store_name,
            self.campaign_name,
            str(self.last_update)
        )
