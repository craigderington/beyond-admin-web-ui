from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, PasswordField, DateField, SelectField
from wtforms.validators import DataRequired, InputRequired, NumberRange, Length
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from models import CampaignType, Store
from sqlalchemy import text


def get_campaign_types():
    stmt = text("SELECT id, name FROM campaigntypes ORDER BY name ASC")
    stmt = stmt.columns(CampaignType.id)
    return CampaignType.query.from_statement(stmt).all()


def get_active_stores():
    stmt = text("SELECT id, name FROM stores where status = 'Active' ORDER BY name ASC")
    stmt = stmt.columns(Store.id, Store.name)
    return Store.query.from_statement(stmt).all()


class UserLoginForm(FlaskForm):
    username = StringField('Username', [InputRequired(message='Username is required.'), Length(min=8, max=64)])
    password = PasswordField('Password', [InputRequired(message='Password is required.'), Length(min=8, max=256)])


class AddCampaignForm(FlaskForm):
    job_number = IntegerField('Job Number:', validators=[DataRequired()])
    client_id = StringField('Client ID:', validators=[DataRequired()])
    name = StringField('Campaign Name:', validators=[DataRequired()])
    campaign_type = IntegerField('Campaign Type ID:', validators=[DataRequired()])
    start_date = DateField('Start Date:', format='%m/%d/%Y', validators=[DataRequired()])
    end_date = DateField('End Date:', format='%m/%d/%Y', validators=[DataRequired()])
    radius = IntegerField('Campaign Radius:', validators=[DataRequired()])
    objective = StringField('Campaign Objective:')
    description = StringField('Campaign Description:')
    store_id = IntegerField('Store ID:', validators=[DataRequired()])
    status = StringField('Status:', validators=[DataRequired()])


class AddStoreForm(FlaskForm):
    client_id = StringField('Client ID:', validators=[DataRequired(message='The client ID is required.')])
    name = StringField('Store Name:', validators=[DataRequired(message='The store name is required.')])
    address1 = StringField('Store Address 1:', validators=[DataRequired(message='The store address is required.')])
    address2 = StringField('Store Address 2:')
    city = StringField('City:', validators=[DataRequired(message='The store city is required.')])
    state = StringField('State:', validators=[DataRequired(message='The state is required.'), Length(min=2, max=2)])
    zip_code = StringField('Zip Code:', validators=[DataRequired(message='The zip code is required.')])
    phone_number = StringField('Phone Number:', validators=[DataRequired(message='The phone number is required.')])
    notification_email = StringField('Notification Email:',
                                     validators=[DataRequired(
                                         message='The notification email address is required to create a new store')])
    simplifi_company_id = IntegerField('SimpliFi ID:')
    simplifi_client_id = StringField('SimpliFi ClientID:')
    simplifi_name = StringField('SimpliFi Name:')
    adf_email = StringField('ADF Email:')
    reporting_email = StringField('Reporting Email:')
    status = StringField('Status:')
