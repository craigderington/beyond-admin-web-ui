from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import DataRequired, InputRequired, NumberRange


class AddCampaignForm(FlaskForm):
    job_number = IntegerField('job_number', [InputRequired(message='Job number must be numeric.'),
                                             NumberRange(min=1000, max=99999999)])
    client_id = StringField('client_id', validators=[DataRequired(message='The client ID is required.')])
    campaign = StringField('campaign', validators=[DataRequired(message='The campaign is required.')])
