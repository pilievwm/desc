from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, abort, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc, asc, and_, or_, not_
from sqlalchemy.exc import OperationalError, NoResultFound
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from oauthlib.oauth2.rfc6749.errors import InvalidClientIdError
from requests.models import MissingSchema
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from flask import Flask, session
from flask_session import Session
from urllib.parse import urlparse
import sys
import generator
import socket
import os
import logging
import traceback



app = Flask(__name__)

# Flask-Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = os.urandom(24) # Secret key for signing session cookies
app.config['SESSION_FILE_DIR'] = 'sessions' # Directory where session files will be stored
app.config['SESSION_PERMANENT'] = False # Session data should not be permanent
app.config['SESSION_USE_SIGNER'] = True # Secure cookies
app.config['SESSION_COOKIE_HTTPONLY'] = True # Prevent client side tampering of session cookies
app.config['SQLALCHEMY_ECHO'] = False


Session(app)

basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, 'database'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database/test.db')
db = SQLAlchemy(app)
session = db.session

login_manager = LoginManager(app)
login_manager.login_view = 'login' # Redirect to Google login if user is not logged in


# Load .env file
load_dotenv()  

socketio = SocketIO(app, manage_session=False)

user_data = {}  # Here's where you'd store user data

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True)

class Project(db.Model):
    __tablename__ = 'project'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    x_cloudcart_apikey = db.Column(db.String(128))
    model = db.Column(db.String(128))
    temperature = db.Column(db.Integer, nullable=True)
    store_url = db.Column(db.String(128))
    website_name = db.Column(db.String(128), nullable=True)
    use_seo_package = db.Column(db.Boolean)
    currency = db.Column(db.String(128))
    length = db.Column(db.Integer)
    test_mode = db.Column(db.Integer)
    print_prompt = db.Column(db.Boolean)
    only_active = db.Column(db.Boolean)
    skip_products_with_description = db.Column(db.Integer)
    only_category = db.Column(db.String(128))
    only_vendor = db.Column(db.String(128))
    language = db.Column(db.String(128))
    niche = db.Column(db.String(128))
    free_delivery_over = db.Column(db.Integer)
    mention_free_delivery_price = db.Column(db.Boolean)
    link_to_product = db.Column(db.Boolean)
    link_to_category = db.Column(db.Boolean)
    link_to_vendor = db.Column(db.Boolean)
    link_to_more_from_same_vendor_and_category = db.Column(db.Boolean)
    use_keywords = db.Column(db.Integer)
    keywords_density = db.Column(db.Integer)
    use_free_keywords = db.Column(db.String(128))
    link_keyword_to_product = db.Column(db.Boolean)
    link_keyword_density = db.Column(db.Integer)
    purpouse = db.Column(db.String(128))
    product_name = db.Column(db.Boolean)
    price_from = db.Column(db.Boolean)
    show_price = db.Column(db.Boolean)
    short_description = db.Column(db.Boolean)
    description = db.Column(db.Boolean)
    vendor_name = db.Column(db.Boolean)
    category_name = db.Column(db.Boolean)
    property_option_values = db.Column(db.Boolean)
    use_website_name = db.Column(db.Boolean)
    user_id = db.Column(db.Integer, nullable=False)
    domain = db.Column(db.String(128))



########## SocketIO ##########


@socketio.on('connect')
def connect_handler():
    user_data[request.sid] = {}  # Initialize user data for this session

@socketio.on('disconnect')
def disconnect_handler():
    if request.sid in user_data:
        del user_data[request.sid]  # Clean up user data for this session

@socketio.on('connect', namespace='/')
def logs_connect():
    socketio.emit('log', {'data': f'Connected to the backend app...'}, namespace='/')

generator.set_socketio(socketio)

# Enable logging
#logging.basicConfig(filename='app.log', level=logging.DEBUG)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

########## Google Login ##########

redirect_uri = os.getenv('GOOGLE_REDIRECT_URI')

blueprint = make_google_blueprint(
    client_id=os.environ['GOOGLE_CLIENT_ID'],
    client_secret=os.environ['CLIET_SECRET'],
    scope=["https://www.googleapis.com/auth/userinfo.email",
           "https://www.googleapis.com/auth/userinfo.profile",
           "openid"],
    redirect_url=redirect_uri,
    reprompt_consent=True,
)
app.register_blueprint(blueprint, url_prefix="/login")

@oauth_authorized.connect_via(blueprint)
def google_logged_in(blueprint, token):
    if not token:
        flash("Failed to log in with Google.", category="error")
        return False

    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        msg = "Failed to fetch user info from Google."
        flash(msg, category="error")
        return False

    google_info = resp.json()
    google_user_id = str(google_info["id"])

    # Find this OAuth token in the database, or create it
    query = User.query.filter_by(email=google_info["email"])
    
    try:
        user = query.one()
    except NoResultFound:
        flash("No user found!", category="error")
        return redirect(url_for('logout'))  # Redirects to an unauthorized page
    

    login_user(user)
    return redirect(url_for('index')) 


########## Database ##########
def create_tables():
    with app.app_context():
        try:
            db.create_all()
            print("Tables created successfully.")
        except OperationalError:
            print("Could not create tables. Make sure your database server is running and your database URI is correct.")

        
# Call the function right after creating the SQLAlchemy object
create_tables()

########## Routes ##########

@app.route('/stop_process', methods=['POST'])
def stop_process():
    generator.stop()  # Call the function from generator.py
    return 'Process stopped.'

@app.route('/')
@login_required
def index():
    projects = Project.query.filter_by(user_id=current_user.id).order_by(desc(Project.id)).all()
    app.logger.info('Render index page')  # Logging example
    return render_template('projects.html', projects=projects)


@app.route('/ai/<int:project_id>')
@login_required
def mypage(project_id):
    project = session.get(Project, project_id)


    # If the project does not exist or does not belong to the current user
    if project is None or project.user_id != current_user.id:
        return index()

    app.logger.info('Render AI page')  # Logging example
    return render_template('ind.html', project=project)

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()

    if not data:
        app.logger.error('No data provided')  # Logging example
        return jsonify({'error': 'No data provided'}), 400

    try:
        generator.app_settings = data.get('app_settings')
        generator.seo_settings = data.get('seo_settings')
        generator.prompt_settings = data.get('prompt_settings')

        generator.calculate_all(generator.app_settings)

        return jsonify({'status': 'success'}), 200
    except KeyError as e:

        socketio.emit('log', {'data': f'Please check your X-CloudCart-ApiKey. It is missing or it is wrong!'}, namespace='/')
        return jsonify({'error': f"The key '{str(e)}' was not found in the data. Please check your data source."}), 500
    except MissingSchema as e:

        socketio.emit('log', {'data': f'{str(e)}'}, namespace='/')
        return jsonify({'error': 'First you need to add some credentials like: X-CloudCart-ApiKey and OpenAI Key!'}), 500
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}'}, namespace='/')
        return jsonify({'error': str(e)}), 500


@app.route('/set', methods=['POST'])
def set_settings():
    data = request.get_json()

    if not data:
        app.logger.error('No data provided')  # Logging example
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Assign the settings
        generator.app_settings = data.get('app_settings')
        generator.seo_settings = data.get('seo_settings')
        generator.prompt_settings = data.get('prompt_settings')

        # Validate the data here if needed...

        # Call the function with the provided settings
        gener = generator.get_all_products(generator.app_settings)

        
        return jsonify({'status': 'success'}), 200
    except KeyError as e:

        socketio.emit('log', {'data': f'Please check your X-CloudCart-ApiKey. It is missing or it is wrong!'}, namespace='/')
        return jsonify({'error': f"The key '{str(e)}' was not found in the data. Please check your data source."}), 500

    except MissingSchema as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}\n{tb}'}, namespace='/')
        return jsonify({'error': 'First you need to add some credentials like: X-CloudCart-ApiKey and OpenAI Key!'}), 500
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}\n{tb}'}, namespace='/')
        return jsonify({'error': str(e)}), 500
    
####### AUTH ROUTES #######
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    flash("You have logged out.", category="success")
    return redirect(url_for('logout'))

####### PROJECTS ROUTES #######

### ADD NEW PROJECT ###
@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        store_url = request.form.get('store_url')
        x_cloudcart_apikey = request.form.get('x_cloudcart_apikey')

        # Extract domain from the URL
        parsed_url = urlparse(store_url)
        domain_only = parsed_url.netloc

        # Query the database to check if a project with the given domain already exists
        existing_project = Project.query.filter(func.lower(Project.domain) == func.lower(domain_only)).first()

        if existing_project is not None:
            # If a project with the given domain already exists, return an error message
            return jsonify({'error': 'A project with this store URL already exists.'}), 400

        # If no existing project was found, create a new project
        project = Project(
            store_url=store_url,
            domain=domain_only,
            x_cloudcart_apikey=x_cloudcart_apikey,
            user_id=current_user.id
        )

        db.session.add(project)
        db.session.commit()

        return jsonify({'message': 'Project successfully created.'})
    
### GET PROJECT ###
@app.route('/projects/<int:project_id>', methods=['GET'])
@login_required
def get_project(project_id):
    project = session.get(Project, project_id)
    return jsonify({
        'store_url': project.store_url,
        'x_cloudcart_apikey': project.x_cloudcart_apikey
    })

### EDIT PROJECT ###
@app.route('/projects/edit/<int:project_id>', methods=['POST'])
@login_required
def edit_project(project_id):
    project = session.get(Project, project_id)

    store_url = request.form.get('editStoreUrl')
    x_cloudcart_apikey = request.form.get('editXCloudCartApiKey')

    project.store_url = store_url
    project.x_cloudcart_apikey = x_cloudcart_apikey

    db.session.commit()

    return jsonify({'message': 'Project successfully updated.'})


### DELETE PROJECT ###
@app.route('/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    project = session.get(Project, project_id)

    if project:
        db.session.delete(project)
        db.session.commit()
        return jsonify({'message': 'Project deleted successfully'}), 200
    else:
        return jsonify({'error': 'Project not found'}), 404

### SAVE SETTINGS ###
@app.route('/save_settings/<int:project_id>', methods=['POST'])
def save_settings(project_id):
    data = request.get_json()
    
    # Attempt to find existing project settings
    session = db.session
    project = session.get(Project, project_id)

    if project is None:
        return jsonify({'message': 'No project found with this ID.'}), 404

    # Flatten data dictionary
    flattened_data = {**data.get('app_settings', {}), **data.get('seo_settings', {}), **data.get('prompt_settings', {})}


    # Define mapping from data keys to database fields
    field_mapping = {
        "X-CloudCart-ApiKey": "x_cloudcart_apikey",
        "model": "model",
        "temperature": "temperature",
        "url": "store_url",
        "website_name": "website_name",
        "use_seo_package": "use_seo_package",
        "currency": "currency",
        "length": "length",
        "test_mode": "test_mode",
        "print_prompt": "print_prompt",
        "only_active": "only_active",
        "skip_products_with_description": "skip_products_with_description",
        "only_category": "only_category",
        "only_vendor": "only_vendor",
        "language": "language",
        "niche": "niche",
        "free_delivery_over": "free_delivery_over",
        "mention_free_delivery_price": "mention_free_delivery_price",
        "link_to_product": "link_to_product",
        "link_to_category": "link_to_category",
        "link_to_vendor": "link_to_vendor",
        "link_to_more_from_same_vendor_and_category": "link_to_more_from_same_vendor_and_category",
        "use_keywords": "use_keywords",
        "keywords_density": "keywords_density",
        "use_free_keywords": "use_free_keywords",
        "link_keyword_to_product": "link_keyword_to_product",
        "link_keyword_density": "link_keyword_density",
        "purpouse": "purpouse",
        "product_name": "product_name",
        "price_from": "price_from",
        "show_price": "show_price",
        "short_description": "short_description",
        "description": "description",
        "vendor_name": "vendor_name",
        "category_name": "category_name",
        "property_option_values": "property_option_values",
        "use_website_name": "use_website_name",
        "domain": "domain_only",
    }

    # Update project settings
    for key, value in flattened_data.items():
        if key in field_mapping:
            setattr(project, field_mapping[key], value)
        
    # Extract domain from store_url
    store_url = flattened_data.get('url')
    if store_url:
        parsed_url = urlparse(store_url)
        domain = parsed_url.netloc
        project.domain = domain

    db.session.commit()

    return jsonify({'message': 'Settings saved successfully.'})




####### END PROJECTS ROUTES #######

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Use the DNS address from the environment variables
    s.connect((os.environ['DNS_ADDRESS'], int(os.environ['DNS_PORT'])))
    ip_address = s.getsockname()[0]
    s.close()
    return ip_address


if __name__ == "__main__":
    if 'create_tables' in sys.argv:
        create_tables()
    else:
        with app.app_context():
            port = int(os.environ.get('PORT'))
            data_dir=os.environ['CERT_DIR']
            host = get_ip_address()
            socketio.run(app, host=host, port=port, debug=True, ssl_context=(os.path.join(data_dir, os.environ['FULLCHAIN_FILE']), os.path.join(data_dir, os.environ['PRIVKEY_FILE'])), allow_unsafe_werkzeug=True)
