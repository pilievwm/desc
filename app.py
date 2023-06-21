from flask import Flask, request, jsonify, render_template
import generator
import socket
import os
import logging
import traceback
from requests.models import MissingSchema
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from flask import Flask, session
from flask_session import Session

app = Flask(__name__)

# Flask-Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = os.urandom(24) # Secret key for signing session cookies
app.config['SESSION_FILE_DIR'] = 'sessions' # Directory where session files will be stored
app.config['SESSION_PERMANENT'] = False # Session data should not be permanent
app.config['SESSION_USE_SIGNER'] = True # Secure cookies

Session(app)


# Load .env file
load_dotenv()  

socketio = SocketIO(app, manage_session=False)

user_data = {}  # Here's where you'd store user data

@socketio.on('connect')
def connect_handler():
    print(f"Client {request.sid} connected")
    user_data[request.sid] = {}  # Initialize user data for this session

@socketio.on('disconnect')
def disconnect_handler():
    print(f"Client {request.sid} disconnected")
    del user_data[request.sid]  # Clean up user data for this session

generator.set_socketio(socketio)

# Enable logging
#logging.basicConfig(filename='app.log', level=logging.DEBUG)


@app.route('/stop_process', methods=['POST'])
def stop_process():
    generator.stop()  # Call the function from generator.py
    return 'Process stopped.'

@app.route('/')
def mypage():
    app.logger.info('Render index page')  # Logging example
    return render_template('ind.html')

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


@socketio.on('connect', namespace='/')
def logs_connect():
    socketio.emit('log', {'data': f'Connected to the backend app...'}, namespace='/')

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Use the DNS address from the environment variables
    s.connect((os.environ['DNS_ADDRESS'], int(os.environ['DNS_PORT'])))
    ip_address = s.getsockname()[0]
    s.close()
    return ip_address


if __name__ == "__main__":
    port = int(os.environ.get('PORT'))
    data_dir=os.environ['CERT_DIR']
    host = get_ip_address()
    socketio.run(app, host=host, port=port, debug=True, ssl_context=(os.path.join(data_dir, os.environ['FULLCHAIN_FILE']), os.path.join(data_dir, os.environ['PRIVKEY_FILE'])), allow_unsafe_werkzeug=True)