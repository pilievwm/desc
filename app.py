from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, abort, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc, asc, and_, or_, not_, case, select, update, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.exc import OperationalError, NoResultFound
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from flask_migrate import Migrate
from oauthlib.oauth2.rfc6749.errors import InvalidClientIdError
from requests.models import MissingSchema
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room, rooms, disconnect
from dotenv import load_dotenv
from flask import Flask, session
from flask_session import Session
from urllib.parse import urlparse
from models import create_statistics, create_user_class, create_project_class, create_processed
import sys
from generator import stop, get_all_products, calculate_all, set_socketio, getCategories, getVendors
import socket
import os
import logging
import traceback
from datetime import datetime
from functools import wraps


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
migrate = Migrate(app, db)
session = db.session
from generator import stop, get_all_products, calculate_all, set_socketio, getCategories, getVendors

login_manager = LoginManager(app)
login_manager.login_view = 'login' # Redirect to Google login if user is not logged in

# Load .env file
load_dotenv()  

########## Database Models ##########
User = create_user_class(db)
Project = create_project_class(db)
Statistics = create_statistics(db)
Processed = create_processed(db)

socketio = SocketIO(app, manage_session=False)


user_data = {}  # Here's where you'd store user data

########## SocketIO ##########


@socketio.on('connect', namespace='/')
def connect_handler():
    emit('connect', {'data': 'Waiting for project_id to join the corresponding project.'}, namespace='/')

@socketio.on('join', namespace='/')
def on_join(data):
    room = data['project_id']
    username = data['username']
    join_room(room)
    emit('log', {'data': f'{username} has entered the project.'}, room=room)

@socketio.on('disconnect', namespace='/')
def disconnect_handler():
    # This assumes that the disconnecting user can only be in one room
    # If a user can be in multiple rooms, you should store a list of rooms that a user is in and iterate over it here
    for room in rooms(sid=request.sid, namespace='/'):
        leave_room(room, sid=request.sid, namespace='/')
        emit('log', {'data': f'User with session id {request.sid} has left project id {room}'}, room=room, namespace='/')

set_socketio(socketio)

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

def super_user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.super_user:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

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
@login_required
def stop_process():
    project_id = request.json.get('project_id')
    stop(project_id)
    project = db.session.query(Project).get(project_id)
    if project:
        project.in_progress = False
        db.session.commit()
    return 'Process stopped.'

@app.route('/')
@login_required
def index():
    # Define the model names
    model_names = ['gpt-3.5-turbo', 'gpt-4']

    # Get the list of all unique project IDs for the current user, or all projects if the user_id is 1 or 2
    if current_user.id in [1, 2]:  # if the user is 1 or 2, get all project ids
        project_ids = session.query(Project.id).distinct()
    else:  # else get only the current user's project ids
        project_ids = session.query(Project.id).join(User, User.id == Project.user_id).filter(User.id == current_user.id).distinct()

    # Fetch project and user name details for the current user, or all projects if the user_id is 1 or 2
    if current_user.id in [1, 2]:  # if the user is 1 or 2, get all projects
        project_user_data = session.query(Project, User.name).join(User, User.id == Project.user_id).all()
    else:  # else get only the current user's projects
        project_user_data = session.query(Project, User.name).join(User, User.id == Project.user_id).filter(User.id == current_user.id).all()

    statistics = []

    for project_id in project_ids:
        for model_name in model_names:
            stat = session.query(
                Statistics.project_id, 
                Statistics.model,
                func.sum(Statistics.prompt_tokens).label('total_prompt_tokens'),
                func.sum(Statistics.completion_tokens).label('total_completion_tokens'),
                func.sum(Statistics.total_tokens).label('total_tokens'),
                func.sum(Statistics.cost).label('total_cost'),
                func.sum((Statistics.test_mode.isnot(None)).cast(Integer)).label('total_test_mode')
            ).join(Project, Project.id == Statistics.project_id
            ).join(User, User.id == Project.user_id
            ).filter(Project.id == project_id[0],
                    Statistics.model == model_name
            ).group_by(Statistics.project_id,  
                        Statistics.model
            ).first()

            # If stat is None, create an entry with zeros
            if stat is None:
                stat_dict = {
                    'project_id': project_id[0],
                    'model': model_name,
                    'total_prompt_tokens': 0,
                    'total_completion_tokens': 0,
                    'total_tokens': 0,
                    'total_cost': 0.0,
                    'total_test_mode': 0
                }
            else:
                stat_dict = {
                    'project_id': stat.project_id,
                    'model': stat.model,
                    'total_prompt_tokens': stat.total_prompt_tokens,
                    'total_completion_tokens': stat.total_completion_tokens,
                    'total_tokens': stat.total_tokens,
                    'total_cost': stat.total_cost,
                    'total_test_mode': stat.total_test_mode
                }

            statistics.append(stat_dict)

    grouped_statistics = {}
    for stat in statistics:
        if stat['project_id'] not in grouped_statistics:
            grouped_statistics[stat['project_id']] = {
                'gpt-3.5-turbo': {},
                'gpt-4': {}
            }
        grouped_statistics[stat['project_id']][stat['model']] = stat

    projects_statistics = []
    for project, user_name in project_user_data:
        if project.id in grouped_statistics:
            projects_statistics.append((project, user_name, grouped_statistics[project.id]))

    app.logger.info('Render index page')  # Logging example
    return render_template('projects.html', projects_statistics=projects_statistics)  # Pass the list of dictionaries to the template


@app.route('/users')
@login_required
def users():
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/get_status')
def get_status():
    project_id = request.args.get('project_id')  # Retrieve the project_id from the query parameters
    project = session.get(Project, project_id)
    in_progress = project.in_progress
    return jsonify({'in_progress': in_progress})

@app.route('/ai/<int:project_id>')
@login_required
def mypage(project_id):
    project = session.get(Project, project_id)

    # If the project does not exist or does not belong to the current user, and the current user is not a super_user
    if project is None or (project.user_id != current_user.id and not current_user.super_user):
        return index()

    app.logger.info('Render AI page')  # Logging example
    return render_template('ind.html', project=project)


@app.route('/clear_processed_records', methods=['POST'])
@login_required
def clear_processed_records():
    project_id = request.json.get('project_id')
    
    if project_id:
        db.session.query(Processed).filter_by(project_id=project_id).delete()
        db.session.commit()
        return f"All processed records for Project ID {project_id} have been cleared."
    else:
        return "Project ID not provided."

@app.route('/calculate', methods=['POST'])
@login_required
def calculate():
    
    data = request.get_json()
    if not data:
        app.logger.error('No data provided')  # Logging example
        return jsonify({'error': 'No data provided'}), 400
    project_id = request.json.get('project_id')
    try:
        app_settings = data.get('app_settings')
        calculate_all(app_settings, project_id)

        return jsonify({'status': 'success'}), 200
    except KeyError as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'Please check your X-CloudCart-ApiKey. It is missing or it is wrong!'}, room=str(project_id), namespace='/')
        return jsonify({'error': f"The key '{str(e)}' was not found in the data. Please check your data source."}), 500
    except MissingSchema as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}'}, room=str(project_id), namespace='/')
        return jsonify({'error': 'First you need to add some credentials like: X-CloudCart-ApiKey and OpenAI Key!'}), 500
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}'}, room=str(project_id), namespace='/')
        return jsonify({'error': str(e)}), 500


@app.route('/set', methods=['POST'])
@login_required
def set_settings():
    data = request.get_json()

    project_id = data.get('project_id')  # Get project_id from the data
    if not data or not project_id:  # Check if both data and project_id are present
        app.logger.error('No data provided')  # Logging example
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Assign the settings
        app_settings = data.get('app_settings')
        seo_settings = data.get('seo_settings')
        short_description_settings = data.get('short_description_settings')
        prompt_settings = data.get('prompt_settings')

        # Validate the data here if needed...

        # Call the function with the provided settings
        
        get_all_products(db, Statistics, Processed, Project, app_settings, seo_settings, prompt_settings, short_description_settings, project_id)
        
        return jsonify({'status': 'success'}), 200
    except KeyError as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)} Please check your X-CloudCart-ApiKey. It is missing or it is wrong!'},room=str(project_id), namespace='/')
        project = db.session.query(Project).get(project_id)
        if project:
            project.in_progress = False
            db.session.commit()
        return jsonify({'error': f"The key '{str(e)}' was not found in the data. Please check your data source."}), 500

    except MissingSchema as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}\n{tb}'},room=str(project_id), namespace='/')
        project = db.session.query(Project).get(project_id)
        if project:
            project.in_progress = False
            db.session.commit()
        return jsonify({'error': 'First you need to add some credentials like: X-CloudCart-ApiKey and OpenAI Key!'}), 500
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        project = db.session.query(Project).get(project_id)
        if project:
            project.in_progress = False
            db.session.commit()
        socketio.emit('log', {'data': f'{str(e)}\n'},room=str(project_id), namespace='/')
        return jsonify({'error': str(e)}), 500
    


####### PROJECTS ROUTES #######

### ADD NEW PROJECT ###
@app.route('/create_user', methods=['POST'])
@login_required
@super_user_required
def create_user():
    
    data = request.get_json()  # Get data sent as JSON

    # Retrieve data from form submission
    name = data.get('name')
    email = data.get('email')
    is_super_user = data.get('super_user')
    
    # Check if user already exists by email
    existing_user_email = User.query.filter_by(email=email).first()
    if existing_user_email is not None:
        return jsonify({"error": "A user with this email already exists."}), 400

    # Create new user
    new_user = User(name=name, email=email, super_user=is_super_user)
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "User created successfully."}), 200

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@super_user_required
def delete_user(user_id):
    user = User.query.get(user_id)
    if user is None:
        return jsonify({"error": "User not found."}), 404

    db.session.delete(user)
    db.session.commit()
    
    return jsonify({"message": "User deleted successfully."}), 200


@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        store_url = request.form.get('store_url')
        x_cloudcart_apikey = request.form.get('x_cloudcart_apikey')

        if not store_url.startswith(('http://', 'https://')):
            # If the URL doesn't start with http:// or https://, add it
            store_url = 'http://' + store_url

        parsed_url = urlparse(store_url)
        domain_only = parsed_url.netloc

        # Query the database to check if a project with the given domain already exists
        existing_project = Project.query.filter(func.lower(Project.domain) == func.lower(domain_only)).first()

        # If no existing project was found, create a new project
        project = Project(
            store_url=store_url,
            domain=domain_only,
            x_cloudcart_apikey=x_cloudcart_apikey,
            user_id=current_user.id,
            created_at=datetime.now()
        )

        db.session.add(project)
        db.session.commit()

        '''new_statistics = Statistics(
            project_id=project.id,  # Here is where you access the id of the new project
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            record_id=0,
            cost=0
        )

        # Add and commit new statistics to write it to the database
        db.session.add(new_statistics)
        db.session.commit()'''

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
    project.updated_at = datetime.now()

    db.session.commit()

    return jsonify({'message': 'Project successfully updated.'})


### DELETE PROJECT ###
@app.route('/projects/<int:project_id>', methods=['DELETE'])
@login_required
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
@login_required
def save_settings(project_id):
    data = request.get_json()
    
    # Attempt to find existing project settings
    session = db.session
    project = session.get(Project, project_id)

    if project is None:
        return jsonify({'message': 'No project found with this ID.'}), 404

    # Flatten data dictionary
    flattened_data = {**data.get('app_settings', {}), **data.get('seo_settings', {}), **data.get('prompt_settings', {}), **data.get('short_description_settings', {})}


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
        "only_category_name": "only_category_name",
        "only_vendor": "only_vendor",
        "only_vendor_name": "only_vendor_name",
        "specific_product": "specific_product",
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
        "enable_product_description": "enable_product_description",
        "enable_generate_meta_description": "enable_generate_meta_description",
        "enable_product_short_description": "enable_product_short_description",
        "short_purpose": "short_purpose",
        "short_length": "short_length",
        "short_temperature": "short_temperature",
        "short_language": "short_language",
        "short_product_name": "short_product_name",
        "short_short_description": "short_short_description",
        "short_vendor_name": "short_vendor_name",
        "short_category_name": "short_category_name",
        "short_property_option_values": "short_property_option_values",
        "short_use_website_name": "short_use_website_name",
        "short_additional_instructions": "short_additional_instructions",
        "additional_instructions": "additional_instructions",
        "system_instructions": "system_instructions",
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
    project.updated_at = datetime.now()

    db.session.commit()

    return jsonify({'message': 'Settings saved successfully.'})

@app.route('/get_all_categories', methods=['POST'])
@login_required
def get_categories():
    data = request.get_json()
    if not data:  # Check if both data and project_id are present
        app.logger.error('No data provided')  # Logging example
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Assign the settings
        app_settings = data.get('app_settings')
        categories = getCategories(app_settings)
        return jsonify({'status': 'success', 'categories': categories}), 200  # return products in the response
    except KeyError as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}\n{tb}'}, namespace='/')
        app.logger.error('KeyError: ' + str(e))  # Logging example
        return jsonify({'status': 'error', 'message': 'A KeyError occurred'}), 500  # return an error status in case of a KeyError 

@app.route('/get_all_vendors', methods=['POST'])
@login_required
def get_vendors():
    data = request.get_json()
    if not data:  # Check if both data and project_id are present
        app.logger.error('No data provided')  # Logging example
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Assign the settings
        app_settings = data.get('app_settings')
        vendors = getVendors(app_settings)
        return jsonify({'status': 'success', 'vendors': vendors}), 200  # return products in the response
    except KeyError as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}\n{tb}'}, namespace='/')
        app.logger.error('KeyError: ' + str(e))  # Logging example
        return jsonify({'status': 'error', 'message': 'A KeyError occurred'}), 500  # return an error status in case of a KeyError 



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
