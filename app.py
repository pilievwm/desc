from flask import Flask, request, jsonify, render_template
import generator
import socket

import logging
import traceback
from requests.models import MissingSchema
from flask_socketio import SocketIO, emit



            
app = Flask(__name__)
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

        socketio.emit('log', {'data': f'{str(e)}'}, namespace='/')
        return jsonify({'error': 'First you need to add some credentials like: X-CloudCart-ApiKey and OpenAI Key!'}), 500
    except Exception as e:
        tb = traceback.format_exc()  # get the traceback
        socketio.emit('log', {'data': f'{str(e)}'}, namespace='/')
        return jsonify({'error': str(e)}), 500


@socketio.on('connect', namespace='/')
def logs_connect():
    socketio.emit('log', {'data': f'Connected to the backend app...'}, namespace='/')

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Use the DNS address from the environment variables
    s.connect(('8.8.8.8', 80))  # Notice the tuple
    ip_address = s.getsockname()[0]
    s.close()
    return ip_address


if __name__ == "__main__":
    host = '0.0.0.0'
    socketio.run(app, port=5052, host=host, debug=True, ssl_context=('cert/fullchain.pem', 'cert/privkey.pem'), allow_unsafe_werkzeug=True)