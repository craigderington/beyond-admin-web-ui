import os

basedir = os.path.abspath(os.path.dirname(__file__))

# Your App secret key
SECRET_KEY = os.urandom(64)

# The SQLAlchemy connection string.
SQLALCHEMY_DATABASE_URI = 'mysql://user:password@localhost/earl'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Mongo DB
MONGO_SERVER = 'localhost'
MONGO_DB = 'earl-pixel-tracker'
SECRET_KEY = os.urandom(64)

# Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Flask-WTF flag for CSRF
CSRF_ENABLED = True

# App name
APP_NAME = "EARL Web Frontend"

#---------------------------------------------------
# Image and file configuration
#---------------------------------------------------
# The file upload folder, when using models with files
UPLOAD_FOLDER = basedir + '/app/static/uploads/'

# The image upload folder, when using models with images
IMG_UPLOAD_FOLDER = basedir + '/app/static/uploads/'

# The image upload url, when using models with images
IMG_UPLOAD_URL = '/static/uploads/'


