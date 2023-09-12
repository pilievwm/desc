from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, abort, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func, desc, asc, and_, or_, not_, case, select, update, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.exc import OperationalError, NoResultFound
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from flask_migrate import Migrate
from oauthlib.oauth2.rfc6749.errors import InvalidClientIdError
from requests.models import MissingSchema
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room, rooms, disconnect
from config import Config
from dotenv import load_dotenv
from flask import Flask, session, make_response
from flask_session import Session
from urllib.parse import urlparse
from models import create_statistics, create_user_class, create_project_class, create_category_class, create_processed, create_processed_category_class, create_category_batch_class
import sys
from generator import stop, get_all_products, calculate_all, set_socketio, getCategories, getVendors, getProducts
from category import stop_category, cat, set_socketio, processCategories
from helpers import get_related_searches
import socket
import os
import logging
import traceback
from datetime import datetime
from functools import wraps
import re

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
from category import cat, set_socketio
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Redirect to Google login if user is not logged in

# Load .env file
load_dotenv()  

########## Database Models ##########
User = create_user_class(db)
Project = create_project_class(db)
Category_Settings = create_category_class(db)
Processed_category = create_processed_category_class(db)
batch_category = create_category_batch_class(db)
Statistics = create_statistics(db)
Processed = create_processed(db)
with app.app_context():
    db.create_all()

socketio = SocketIO(app, manage_session=False)
Config.socketio = socketio

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


@app.route('/stop_category_process', methods=['POST'])
@login_required
def stop_category_process():
    project_id = request.json.get('project_id')
    stop_category(project_id)
    project = db.session.query(Category_Settings).get(project_id)

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
                func.sum((Statistics.test_mode == 1).cast(Integer)).label('total_test_mode')
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

@app.route('/get_batch_status')
def get_batch_status():
    # Get the batch status from the batch_category table
    project_id = request.args.get('project_id')  # Retrieve the project_id from the query parameters

    # Ensure the parameters are provided
    if not project_id:
        return jsonify({'error': 'project_id ais required'}), 400

    # Convert to appropriate type if needed
    project_id = int(project_id)
    type = str('category')
    batch_status = db.session.query(batch_category).filter_by(project_id=project_id, type=type).first()
    
    # Check if a record was found
    if not batch_status:
        print("No matching record found")
        return jsonify({'error': 'No matching record found'}), 200

    batch = batch_status.batch
    return jsonify({'batch': batch})


@app.route('/kill_batch_process', methods=['POST'])
@login_required
def kill_process():
    project_id = request.form.get('project_id')
    type = request.form.get('type')

    if not project_id or not type:
        return jsonify({'error': 'project_id and type are required'}), 400

    try:
        # After killing the process, update the batch status:
        batch_status = session.query(batch_category).filter_by(project_id=project_id, type=type).first()
        
        if not batch_status:
            return jsonify({'error': 'No matching record found for given project_id and type'}), 404

        batch_status.kill_process = True
        db.session.commit()
        socketio.emit('log', {'data': f'Batch process killed. It will stop after the current process is completed...'}, room=str(project_id), namespace='/')
        return jsonify({'status': 'success', 'message': 'Process killed and batch status updated'}), 200

    except Exception as e:
        # Log the exception for debugging
        print(str(e))
        return jsonify({'error': 'An unexpected error occurred while processing the request'}), 500




@app.route('/get_category_status')
def get_category_status():
    project_id = request.args.get('project_id')  # Retrieve the project_id from the query parameters
    category_id = request.args.get('category_id')  # Retrieve the category_id from the query parameters
    project = Category_Settings.query.filter_by(project_id=project_id, category_id=category_id).first()
    in_progress = project.in_progress
    return jsonify({'in_progress': in_progress})


### AGGREGATE CATEGORIES ###
@app.route('/project/<int:project_id>/aggregate', methods=['POST'])
def aggregateCategories(project_id):
    project = session.get(Project, project_id)
    
    if project is None or (project.user_id != current_user.id and not current_user.super_user):
        return index()
    
    # Call the function processCategories to process the categories.
    processCategories(db, Processed_category, Category_Settings, project_id, project.x_cloudcart_apikey, project.store_url, project.model)


    # Return a success message or any other required response
    return jsonify({'status': 'Categories processed successfully'}), 200


### GENERATE PRODUCT DESCRIPTION PAGE ###
@app.route('/ai/<int:project_id>', methods=['GET'])
@login_required
def mypage(project_id):
    project = session.get(Project, project_id)

    # If the project does not exist or does not belong to the current user, and the current user is not a super_user
    if project is None or (project.user_id != current_user.id and not current_user.super_user):
        return index()

    # Update project attributes if they exist in request arguments and in the project object
    for key, value in request.args.items():
        if hasattr(project, key):
            setattr(project, key, value)
            # If you need to save the changes to the database, do so here.
            # For example: session.commit()

    app.logger.info('Render AI page')  # Logging example
    return render_template('ind.html', project=project)



### PROJECT MAIN PAGE ###
@app.route('/project/<int:project_id>')
@login_required
def project(project_id):
    project = session.get(Project, project_id)

    # Define a mapping between app_settings keys and project attributes
    settings_mapping = {
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
        "use_feature_desc": "use_feature_desc",
        "use_interesting_fact": "use_interesting_fact",
        "use_hidden_benefit": "use_hidden_benefit",
        "e_e_a_t": "e_e_a_t",
        "max_property_values": "max_property_values",
        "max_keywords": "max_keywords",
        "max_order_pages": "max_order_pages",
        "description_length": "description_length",
        "include_sales_info": "include_sales_info",
        "only_active_products": "only_active_products",
        "include_category_info": "include_category_info",
        "include_intro": "include_intro",
        "interesting_fact": "interesting_fact",
    }

    # Populate app_settings with values from the project object
    app_settings = {}
    if project:
        for setting_key, project_attr in settings_mapping.items():
            app_settings[setting_key] = getattr(project, project_attr, None)

    
    # Modify the stats query to include additional filtering criteria
    filtered_stats = session.query(Statistics).filter_by(
        task_id='product', 
        project_id=project_id, 
        test_mode=0
    ).distinct(Statistics.record_id).all()

    #totalproducts = getProducts(app_settings, project_id)

    # Get the count of the filtered stats


    # Base query to get all processed categories filtered by project_id
    #categories_query = session.query(Processed_category).join(Category_Settings, 
    #                                Processed_category.category_id == Category_Settings.category_id, 
    #                                isouter=True).filter(Processed_category.project_id == project_id)

    #processed = categories_query.filter(Processed_category.category_update == 1, Category_Settings.category_ready == 0).count()
    #not_processed = categories_query.filter(Processed_category.category_id, Category_Settings.category_id == None).count()
    
    # Execute the query to get the categories
    #categories = categories_query.all()

    #processed_products_count = len(filtered_stats)
    
    #categories = session.query(Category_Settings).filter_by(project_id=project_id).first()

    #processed_categories_count = session.query(Processed_category).filter_by(project_id=project_id, category_test_mode=0).count()

    #processed_test_mode_categories_count = session.query(Processed_category).filter((Processed_category.project_id == project_id) & (Processed_category.category_test_mode.is_(None))).count()




    # If the project does not exist or does not belong to the current user, and the current user is not a super_user
    if project is None or (project.user_id != current_user.id and not current_user.super_user):
        return index()

    app.logger.info('Render Category page')  # Logging example
    return render_template('project_main.html', project=project, stats=filtered_stats, app_settings=app_settings, project_id=project_id)


# UPDATE CATEGORY SETTINGS
@app.route('/processed_categories/update/<int:project_id>/<int:category_id>', methods=['POST'])
@login_required
def update_keywords(project_id, category_id):
    edited_keywords = request.form.get('edited_keywords')
    print(f"Edited keywords... {project_id}, {category_id}")
    # Update the category_keywords in the database
    target_category = session.query(Processed_category).filter_by(project_id=project_id, category_id=category_id).first()
    print(f"target category {target_category}")
    if target_category:
        target_category.category_keywords = edited_keywords
        db.session.commit()
        print("Category keywords updated successfully")
        # Here, add any other logic you want, like a flash message to notify the user of the successful update.
    
    # Redirect back to the page or wherever you want after updating
    return redirect(url_for('processed_categories', project_id=project_id))


### LIST PROCESSED CATEGORIES ###
@app.route('/processed_categories/<int:project_id>/', defaults={'page': 1}, methods=['GET'])
@app.route('/processed_categories/<int:project_id>/<int:page>', methods=['GET'])
@login_required
def processed_categories(project_id, page=1):

    per_page = 30  # Number of items per page

    # Get the saved status filter from the cookie
    saved_status_filter = request.cookies.get('status_filter', None)
    
    # Check if 'status' is in the request arguments. If not, fallback to the saved cookie value
    status_filter = request.args.get('status') if 'status' in request.args else saved_status_filter
    
    # Base query to get all processed categories filtered by project_id
    categories_query = session.query(Processed_category).join(Category_Settings, 
                                    Processed_category.category_id == Category_Settings.category_id, 
                                    isouter=True).filter(Processed_category.project_id == project_id)
    
    # Apply filters based on status
    if status_filter:
        if status_filter == "Processed":
            categories_query = categories_query.filter(Processed_category.category_update == 1, 
                                                       Category_Settings.category_ready == 0)
        elif status_filter == "Working on it":
            categories_query = categories_query.filter(Category_Settings.test_mode == 1)
        elif status_filter == "Ready for Processing":
            categories_query = categories_query.filter(Category_Settings.test_mode == 0, 
                                                       Category_Settings.category_ready == 1)
        elif status_filter == "Not Configured":
            categories_query = categories_query.filter(Processed_category.category_id, 
                                                         Category_Settings.category_id == None)
            
    # Add search functionality
    search_query = request.args.get('search', '').lower()  # Convert search term to lowercase
    print(search_query)
    if search_query:
        categories_query = categories_query.filter(func.lower(Processed_category.category_name).ilike(f"%{search_query}%"))




    # Calculate offset for the query
    offset = (page - 1) * per_page
    total_categories = categories_query.count()
    total_pages = -(-total_categories // per_page)  # Ceiling division

    # Fetch the categories for the current page
    categories = categories_query.order_by(Processed_category.id.desc()).limit(per_page).offset(offset).all()
    
    # Fetch all Category_Settings records and transform them into a dictionary
    category_settings_list = session.query(Category_Settings).filter_by(project_id=project_id).all()
    category_settings_dict = {setting.category_id: setting for setting in category_settings_list}

    # Render the template and pass required variables
    response = make_response(render_template('processed_categories.html', categories=categories, current_page=page, total_pages=total_pages, total_categories=total_categories, project_id=project_id, category_settings=category_settings_dict, status_filter=status_filter, search=search_query))

    if status_filter:
        response.set_cookie('status_filter', str(status_filter))
    else:
        # Set the cookie's expiration to a past date to delete it
        response.set_cookie('status_filter', '', expires=0)

    return response


@app.route('/processed_products/<int:project_id>/', defaults={'page': 1}, methods=['GET'])
@app.route('/processed_products/<int:project_id>/<int:page>', methods=['GET'])
@login_required
def processed_products(project_id, page=1):
    per_page = 30  # Number of items per page

    # Fetch the search query
    search_query = request.args.get('search', '').lower()

    # Base query to get all processed products filtered by project_id
    products_query = session.query(Processed).filter(Processed.project_id == project_id)

    # If there's a search query, filter the products by name or ID
    if search_query:
        try:
            # Try to convert search_query to an integer to search by product ID
            product_id = int(search_query)
            products_query = products_query.filter(
                or_(func.lower(Processed.title).like(f"%{search_query}%"),
                    Processed.record_id == product_id)
            )
        except ValueError:
            # If the search_query can't be converted to int, then just search by name
            products_query = products_query.filter(func.lower(Processed.title).like(f"%{search_query}%"))

    total_products = products_query.count()
    total_pages = -(-total_products // per_page)  # Ceiling division

    # Calculate offset for the query
    offset = (page - 1) * per_page

    # Fetch the products for the current page
    products = products_query.order_by(Processed.id.desc()).limit(per_page).offset(offset).all()

    # Render the template and pass required variables
    response = make_response(render_template('processed_products.html', products=products, current_page=page, total_products=total_products, total_pages=total_pages, project_id=project_id, search=search_query))

    return response





@app.route('/batch_processing/<int:project_id>', methods=['POST'])
@login_required
def batch_processing(project_id):
    try:
        openai_key = request.form.get('openai_key')  # Get openai_key from the form data
        socketio.emit('log', {'data': f'Batch process started'}, room=str(project_id), namespace='/')
        if not openai_key:
            raise ValueError("Missing OpenAI key in the request.")

        # Fetch categories that are ready for processing
        categories = session.query(Category_Settings).filter_by(project_id=project_id, test_mode=0, category_ready=1).all()

        # Counter to keep track of successfully processed categories
        success_count = 0

        for category in categories:

            batch_status = session.query(batch_category).filter_by(project_id=project_id, type="category").first()
            if batch_status and batch_status.kill_process:
                # Set kill_process back to False and commit the change
                batch_status.kill_process = False
                db.session.commit()
                break

            # Update the batch_category table with the current category_id at column batch with True
            # Check if a record with the given project_id and category_id already exists
            existing_category = batch_category.query.filter_by(project_id=project_id, type='category').first()

            if existing_category:
                # Update the batch field of the existing record
                existing_category.batch = True
            else:
                # Create a new record if none exists with the given project_id and category_id
                new_category = batch_category(project_id=project_id, type='category', batch=True)
                db.session.add(new_category)

            # Commit the changes to the database
            db.session.commit()

            # Construct the data structure for each category here
            data = {
                "app_settings": {
                    "X-CloudCart-ApiKey": category.x_cloudcart_apikey,
                    "openai_key": openai_key,  # This should be passed as an argument or fetched differently as it's not in the schema
                    "model": category.model,
                    "seo_model": category.seo_model,
                    "temperature": category.temperature,
                    "url": category.url,
                    "website_name": category.website_name,
                    "use_seo_faq_package": category.use_seo_faq_package,
                    "use_seo_package": category.use_seo_package,
                    "length": category.length,
                    "test_mode": category.test_mode,
                    "print_prompt": category.print_prompt,
                    "only_active": category.only_active_products,
                    "skip_products_with_description": None,  # This attribute isn't clear from the schema
                    "specific_product": None,  # This attribute isn't clear from the schema
                    "category_id": category.category_id,
                    "category_name": category.category_name,
                    "only_vendor": None,  # This attribute isn't clear from the schema
                    "only_vendor_name": None,  # This attribute isn't clear from the schema
                    "language": category.language,
                    "niche": None,  # This attribute isn't clear from the schema
                    "free_delivery_over": None,  # This attribute isn't clear from the schema
                    "mention_free_delivery_price": None,  # This attribute isn't clear from the schema
                    "enable_category_description": category.enable_category_description,
                    "enable_generate_meta_description": category.enable_generate_meta_description,
                    "print_scraped_data": category.print_scraped_data,
                },
                "seo_settings": {
                    "include_category_name_at_headings": category.include_category_name_at_headings,
                    "generate_keywords": category.generate_keywords,
                    "top_brands_links": category.top_brands_links,
                    "generic_keywords": category.generic_keywords,
                    "max_keywords": category.max_keywords,
                    "category_links": None,  # This attribute isn't clear from the schema
                    "wiki_links": category.wiki_links,
                    "cat_links": category.cat_links,
                    "e_e_a_t": category.e_e_a_t,
                },
                "category_settings": {
                    "category_id": category.category_id,
                    "category_name": category.category_name,
                    "include_properties": category.include_properties,
                    "include_properties_faq": category.include_properties_faq,
                    "max_props": category.max_props,
                    "max_property_values": category.max_property_values,
                    "max_property_values_faq": category.max_property_values_faq,
                    "max_keywords": category.max_keywords,
                    "max_order_pages": category.max_order_pages,
                    "description_length": category.description_length,
                    "include_sales_info": category.include_sales_info,
                    "only_active_products": category.only_active_products,
                    "include_category_info": category.include_category_info,
                    "enable_faq_generation": category.enable_faq_generation,
                    "add_faq": category.add_faq,
                    "add_best_selling_products": category.add_best_selling_products,
                    "add_top_brands": category.add_top_brands,
                    "number_images": category.number_images,
                    "use_main_keywords": category.use_main_keywords,
                    "include_faq_info": category.include_faq_info,
                    "include_intro": category.include_intro,
                    "interesting_fact": category.interesting_fact,
                    "add_top_brands_faq": category.add_top_brands_faq,
                    "add_best_selling_products_faq": category.add_best_selling_products_faq,
                    "include_category_info_faq": category.include_category_info_faq,
                    "additional_instructions_faq": category.additional_instructions_faq,
                    "faq_length": category.faq_length,
                    "faq_top_brands_links": category.faq_top_brands_links,
                    "faq_brand_link_authority": category.faq_brand_link_authority,
                    "faq_wiki_link_authority": category.faq_wiki_link_authority,
                    "faq_category_links": category.faq_category_links,
                    "faq_use_schema": category.faq_use_schema,
                    "faq_include_category_name_at_headings": category.faq_include_category_name_at_headings,
                    "max_props_faq": category.max_props_faq,
                    "max_property_values_faq": category.max_property_values_faq,
                    "include_properties_faq": category.include_properties_faq,
                    "enable_additional_instructions": category.enable_additional_instructions,
                    "append_faq": category.append_faq,
                }
            }
            
           # Call the cat function directly
            cat(db, Processed_category, Category_Settings, data['app_settings'], data['category_settings'], data['seo_settings'], project_id)
            
            success_count += 1
        batch_category.query.filter_by(project_id=project_id, type='category').update({'batch': False, 'kill_process': False})
        db.session.commit()
        return jsonify({"message": f"Batch processing completed. Successfully processed {success_count} out of {len(categories)} categories."}), 200

    except ValueError as e:
        socketio.emit('log', {'data': f'Error: {str(e)}'}, room=str(project_id), namespace='/')
        batch_category.query.filter_by(project_id=project_id, type='category').update({'batch': False, 'kill_process': False})
        db.session.commit()
        return jsonify({'error': str(e)}), 400
    
    except Exception as e:
        socketio.emit('log', {'data': f'Error: {str(e)}'}, room=str(project_id), namespace='/')
        batch_category.query.filter_by(project_id=project_id, type='category').update({'batch': False, 'kill_process': False})
        db.session.commit()
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500









### GENERATE NEW CATEGORY DESCRIPTION PAGE ###
@app.route('/cat/<int:project_id>')
@login_required
def catPage(project_id):
    project = session.get(Project, project_id)
    category = session.query(Category_Settings).filter_by(project_id=project_id).first()
    
    # If the project does not exist or does not belong to the current user, and the current user is not a super_user
    if project is None or (project.user_id != current_user.id and not current_user.super_user):
        return index()

    app.logger.info('Render Category page')  # Logging example
    return render_template('category.html', project=project, category=category)


### SPECIFIC CATEGORY PAGE ###
@app.route('/cat/<int:project_id>/<int:category_id>')
@login_required
def categoryPage(project_id, category_id):
    # Fetch the project and category based on the provided IDs
    project = session.get(Project, project_id)
    app.logger.info(f'Querying for project_id: {project_id} and category_id: {category_id}')
    category = session.query(Category_Settings).filter_by(project_id=project_id).filter_by(category_id=category_id).first()

    app.logger.info(f'Result of category query: {category}')

    if category is None:
        # Fetch the actual category_id and category_name from the Processed_category table
        category = session.query(Processed_category).filter_by(project_id=project_id, category_id=category_id).first()

        # Fetch the first row from Category_Settings
        first_category_setting = session.query(Category_Settings).filter_by(project_id=project_id).first()

        if first_category_setting:
            # Copy all attributes except for category_name, category_id, and use_main_keywords
            for column in Category_Settings.__table__.columns:
                if column.name not in ["category_name", "category_id", "use_main_keywords"]:
                    setattr(category, column.name, getattr(first_category_setting, column.name))

            app.logger.info(f'Modified category object: {category}')
        


    # Check if the project exists and belongs to the current user or if the current user is a super_user
    if project is None or (project.user_id != current_user.id and not current_user.super_user):
        return index()

    # Check if the category exists and is associated with the given project
    #if category is None or category.project_id != project_id:
    #    return index()  # or redirect to another page with an error message

    app.logger.info(f'Render Category page for category_id: {category_id}')  # Logging example
    return render_template('category_id.html', project=project, category=category)


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
        socketio.emit('log', {'data': f'Error: Please check your X-CloudCart-ApiKey. It is missing or it is wrong!'}, room=str(project_id), namespace='/')
        return jsonify({'error': f"The key '{str(e)}' was not found in the data. Please check your data source."}), 500
    except MissingSchema as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'Error: {str(e)}'}, room=str(project_id), namespace='/')
        return jsonify({'error': 'First you need to add some credentials like: X-CloudCart-ApiKey and OpenAI Key!'}), 500
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'Error: {str(e)}'}, room=str(project_id), namespace='/')
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
        socketio.emit('log', {'data': f'{str(e)} {tb} Error: Please check your X-CloudCart-ApiKey. It is missing or it is wrong!'},room=str(project_id), namespace='/')
        project = db.session.query(Project).get(project_id)
        if project:
            project.in_progress = False
            db.session.commit()
        return jsonify({'error': f"The key '{str(e)}' {tb} was not found in the data. Please check your data source."}), 500

    except MissingSchema as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'Error: {str(e)}\n{tb}'},room=str(project_id), namespace='/')
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
        socketio.emit('log', {'data': f'Error: {str(e)}\n{tb}'},room=str(project_id), namespace='/')
        return jsonify({'error': str(e)}), 500
    
@app.route('/set_cat', methods=['POST'])
@login_required
def set_settings_category():
    data = request.get_json()
    
    project_id = data.get('project_id')  # Get project_id from the data
    if not data or not project_id:  # Check if both data and project_id are present
        app.logger.error('No data provided')  # Logging example
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Assign the settings
        app_settings = data.get('app_settings')
        seo_settings = data.get('seo_settings')
        #short_description_settings = data.get('short_description_settings')
        #prompt_settings = data.get('prompt_settings')
        category_settings = data.get('category_settings')

        category_id = category_settings.get('category_id')

        # Validate the data here if needed...

        # Call the function with the provided settings
        cat(db, Processed_category, Category_Settings, app_settings, category_settings, seo_settings, project_id)
        
        return jsonify({'status': 'success'}), 200
    except KeyError as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)} {tb}'},room=str(project_id), namespace='/')
        project = Category_Settings.query.filter_by(project_id=project_id, category_id=category_id).first()
        if project:
            project.in_progress = False
            db.session.commit()
        return jsonify({'error': f"The key '{str(e)}' {tb} was not found in the data. Please check your data source."}), 500
    except MissingSchema as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'Error: {str(e)}\n{tb}'},room=str(project_id), namespace='/')
        project = Category_Settings.query.filter_by(project_id=project_id, category_id=category_id).first()
        if project:
            project.in_progress = False
            db.session.commit()
        return jsonify({'error': 'First you need to add some credentials like: X-CloudCart-ApiKey and OpenAI Key!'}), 500
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        project = Category_Settings.query.filter_by(project_id=project_id, category_id=category_id).first()
        if project:
            project.in_progress = False
            db.session.commit()
        socketio.emit('log', {'data': f'Error: {str(e)}\n{tb}'},room=str(project_id), namespace='/')
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


@app.route('/projects/new', methods=['POST'])
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
    flattened_data = {**data.get('app_settings', {}), **data.get('seo_settings', {}), **data.get('prompt_settings', {}), **data.get('short_description_settings', {}), **data.get('category_settings', {})}


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
        "use_feature_desc": "use_feature_desc",
        "use_interesting_fact": "use_interesting_fact",
        "use_hidden_benefit": "use_hidden_benefit",
        "e_e_a_t": "e_e_a_t",
        "max_property_values": "max_property_values",
        "max_keywords": "max_keywords",
        "max_order_pages": "max_order_pages",
        "description_length": "description_length",
        "include_sales_info": "include_sales_info",
        "only_active_products": "only_active_products",
        "include_category_info": "include_category_info",
        "include_intro": "include_intro",
        "interesting_fact": "interesting_fact",


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

@app.route('/save_settings_categories/<int:project_id>', methods=['POST'])
@login_required
def save_settings_categories(project_id):
    data = request.get_json()
    app.logger.info(f'Got data: {data}')
    # Extract the category_id from the data
    category_id = data.get("category_settings", {}).get("category_id")

    if not category_id:
        # Handle the case where category_id is not provided
        return jsonify({"error": "category_id is missing"}), 400
    
    session = db.session
    user_id_tuple = session.query(Project.user_id).filter_by(id=project_id).one()
    user_id = user_id_tuple[0]     

    try:
        # Attempt to get the existing project with the given project_id and category_id
        project = session.query(Category_Settings).filter_by(project_id=project_id).filter_by(category_id=category_id).one()
        app.logger.info(f'Found existing project with project_id: {project_id} and category_id: {category_id}')
    except NoResultFound:
        # If it doesn't exist, create a new one
        project = Category_Settings(project_id=project_id, user_id=user_id, category_id=category_id)
        session.add(project)
    
    
    # Flatten data dictionary
    flattened_data = {**data.get('app_settings', {}),  **data.get('category_settings', {}), **data.get('seo_settings', {})}
    
    # Define mapping from data keys to database fields
    field_mapping = {
        "X-CloudCart-ApiKey": "x_cloudcart_apikey",
        "model": "model",
        "seo_model": "seo_model",
        "length": "length",
        "threshold_lenght": "threshold_lenght",
        "temperature": "temperature",
        "url": "url",
        "website_name": "website_name",
        "test_mode": "test_mode",
        "print_prompt": "print_prompt",
        "only_active": "only_active",
        "category_id": "category_id",
        "category_name": "category_name",
        "language": "language",
        "max_property_values": "max_property_values",
        "max_keywords": "max_keywords",
        "max_order_pages": "max_order_pages",
        "description_length": "description_length",
        "include_sales_info": "include_sales_info",
        "only_active_products": "only_active_products",
        "include_category_info": "include_category_info",
        "enable_category_description": "enable_category_description",
        "enable_generate_meta_description": "enable_generate_meta_description",
        "print_scraped_data": "print_scraped_data",
        "enable_faq_generation": "enable_faq_generation",
        "add_faq": "add_faq",
        "add_best_selling_products": "add_best_selling_products",
        "add_top_brands": "add_top_brands",
        "number_images": "number_images",
        "include_category_name_at_headings": "include_category_name_at_headings",
        "top_brands_links": "top_brands_links",
        "generate_keywords": "generate_keywords",
        "generic_keywords": "generic_keywords",
        "category_links": "category_links",
        "wiki_links": "wiki_links",
        "cat_links": "cat_links",
        "use_seo_package": "use_seo_package",
        "additional_instructions": "additional_instructions",
        "e_e_a_t": "e_e_a_t",
        "max_props": "max_props",
        "include_properties": "include_properties",
        "use_main_keywords": "use_main_keywords",
        "include_faq_info": "include_faq_info",
        "add_top_brands_faq": "add_top_brands_faq",
        "add_best_selling_products_faq": "add_best_selling_products_faq",
        "include_category_info_faq": "include_category_info_faq",
        "additional_instructions_faq": "additional_instructions_faq",
        "faq_length": "faq_length",
        "use_seo_faq_package": "use_seo_faq_package",
        "faq_top_brands_links": "faq_top_brands_links",
        "faq_category_links": "faq_category_links",
        "faq_wiki_link_authority": "faq_wiki_link_authority",
        "faq_use_schema": "faq_use_schema",
        "faq_include_category_name_at_headings": "faq_include_category_name_at_headings",
        "faq_brand_link_authority": "faq_brand_link_authority",
        "max_props_faq": "max_props_faq",
        "max_property_values_faq": "max_property_values_faq",
        "include_properties_faq": "include_properties_faq",
        "include_faq_info": "include_faq_info",
        "include_intro": "include_intro",
        "interesting_fact": "interesting_fact",
        "enable_additional_instructions": "enable_additional_instructions",
        "append_faq": "append_faq",

    }

    
    # Update project settings
    for key, value in flattened_data.items():
        if key in field_mapping:
            setattr(project, field_mapping[key], value)

    
    project.updated_at = datetime.now()
    project.category_ready = True
    session.commit()
    
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
