"""
RTC Signaling server

It creates a webscoket server that is used as signaling for
two RTC peers in order to establish a connection. The main function
is to send data to client no processing
"""

from flask import Flask, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'


socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    # async_mode="eventlet" # TODO: need to install eventlet
)


@socketio.on_error_default
def default_error_handler(e):
    print(e)
    print(request.event["message"])
    print(request.event["args"])
    
@socketio.on('connect', namespace='/rtc')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect', namespace='/rtc')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")


@socketio.on('message', namespace='/rtc')
def handle_message(data):
    """
    Handle incoming message
    """
    print("\n### Message")
    print(data)
    print("### Message\n")
    
    emit('response', data, include_self=False)
    

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8000)