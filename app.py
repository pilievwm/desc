from flask import Flask, request, jsonify, render_template
import generator
import socket
import os
import logging
import traceback
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv


            
app = Flask(__name__)

# Load environment variables
load_dotenv('.env')

socketio = SocketIO(app)
generator.set_socketio(socketio)




# Enable logging
#logging.basicConfig(filename='app.log', level=logging.DEBUG)

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
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'>>>Error: 500<<< \n{str(e)}\n{tb}'}, namespace='/')
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
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'>>>Error: 500<<< \n{str(e)}\n{tb}'}, namespace='/')
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
    host = get_ip_address()
    data_dir=os.environ['CERT_DIR']
    socketio.run(app, port=5430, host=host, debug=True, ssl_context=(os.path.join(data_dir, os.environ['FULLCHAIN_FILE']), os.path.join(data_dir, os.environ['PRIVKEY_FILE'])))