import zmq
import json
import threading
import time
from flask import Flask, render_template_string, jsonify

# --- Global State ---
# This dictionary will hold the latest color data.
# It's shared between the Flask app and the ZMQ listener.
latest_color_data = {
    "r": 0,
    "g": 0,
    "b": 0,
    "hex": "#000000",
    "dominant": "None",
    "status": "initializing"
}
# We use a lock to prevent race conditions when two threads
# (Flask and ZMQ) access the global data at the same time.
data_lock = threading.Lock()

# --- IPC File Path ---
IPC_PATH = "ipc:///tmp/color_sensor.ipc"

# --- 1. ZeroMQ Background Thread ---
def zmq_listener():
    """
    Runs in a separate thread.
    Listens for ZMQ messages from the color_sensor.py script.
    """
    global latest_color_data
    print(f"ZMQ listener thread started, connecting to {IPC_PATH}")
    
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    
    # Use 'connect' for the subscriber
    socket.connect(IPC_PATH)
    
    # Subscribe to all messages (empty topic)
    socket.setsockopt_string(zmq.SUBSCRIBE, '')
    
    # Set a 5-second timeout for receiving messages
    socket.setsockopt(zmq.RCVTIMEO, 5000)

    while True:
        try:
            # Wait for a message
            message = socket.recv_string()
            
            # Parse the JSON message
            data = json.loads(message)
            
            # Update the global data with a lock
            with data_lock:
                latest_color_data = data
                latest_color_data["status"] = "receiving"
                
        except zmq.Again:
            # This triggers if no message is received for 5 seconds
            with data_lock:
                latest_color_data["status"] = "not_receiving"
            print("ZMQ: No data received for 5 seconds.")
        except Exception as e:
            print(f"ZMQ Error: {e}")
            with data_lock:
                latest_color_data["status"] = "error"
            time.sleep(1) # Wait a bit before retrying

# --- 2. Flask Web Application ---
app = Flask(__name__)

@app.route('/')
def index():
    """Serves the main HTML page."""
    # The HTML is embedded as a string
    return render_template_string(HTML_TEMPLATE)

@app.route('/data')
def data():
    """
    This is the API endpoint that the webpage's JavaScript will call.
    It returns the latest color data as JSON, formatted for the old JS.
    """
    with data_lock:
        # Create a new dictionary in the format the old JS expects
        js_response = {
            "r": latest_color_data.get("r", 0),
            "g": latest_color_data.get("g", 0),
            "b": latest_color_data.get("b", 0),
            "hex": latest_color_data.get("hex", "#000000"),
            "dominant": latest_color_data.get("dominant", "---"),
            "receiving": latest_color_data.get("status") == "receiving"
        }
        return jsonify(js_response)

# --- 3. HTML, CSS, & JavaScript Template ---
# All in one string for simplicity.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Raspberry Pi Color Sensor</title>
    <!-- Load Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* Custom transition for smooth color changes */
        #color-box {
            transition: background-color 0.5s ease;
        }
    </style>
</head>
<body class="bg-gray-900 text-white font-sans flex items-center justify-center min-h-screen">

    <div class="bg-gray-800 p-8 rounded-lg shadow-2xl w-full max-w-md text-center">
        
        <h1 class="text-3xl font-bold mb-6">Pi Color Sensor</h1>
        
        <!-- This div will show the detected color -->
        <div id="color-box" class="w-full h-48 border-4 border-gray-700 rounded-lg mb-6 shadow-inner" style="background-color: #000000;">
        </div>
        
        <!-- This will show the RGB values -->
        <div class="text-2xl font-mono mb-4" id="rgb-values">
            R: --- G: --- B: ---
        </div>
        
        <!-- This will show the dominant color name -->
        <div class="text-xl mb-6" id="dominant-color">
            Dominant: ---
        </div>

        <!-- This will show the connection status -->
        <div id="status-container" class="p-3 rounded-lg">
            <p id="status-text" class="text-lg font-semibold">Status: Connecting...</p>
        </div>

    </div>

    <script>
        // This script will run in the browser
        
        // Function to fetch data from our Flask server
        async function fetchColorData() {
            // Get references to the HTML elements we want to update
            const colorBox = document.getElementById('color-box');
            const rgbValues = document.getElementById('rgb-values');
            const dominantColor = document.getElementById('dominant-color');
            const statusContainer = document.getElementById('status-container');
            const statusText = document.getElementById('status-text');

            try {
                // Fetch data from the /data endpoint
                const response = await fetch('/data');
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const data = await response.json();

                if (data.receiving) {
                    // We are receiving data!
                    // Update the color box
                    colorBox.style.backgroundColor = data.hex;
                    
                    // Update the text
                    rgbValues.textContent = `R: ${data.r} G: ${data.g} B: ${data.b}`;
                    dominantColor.textContent = `Dominant: ${data.dominant}`;
                    
                    // Update status
                    statusText.textContent = 'Status: Receiving Data';
                    statusContainer.className = 'p-3 rounded-lg bg-green-700 text-green-100';

                } else {
                    // We are not receiving data
                    statusText.textContent = 'Status: Not Receiving Data';
                    statusContainer.className = 'p-3 rounded-lg bg-red-700 text-red-100';
                }

            } catch (error) {
                // An error occurred (e.g., server is down)
                console.error('Fetch error:', error);
                statusText.textContent = 'Status: Server Unreachable';
                statusContainer.className = 'p-3 rounded-lg bg-red-700 text-red-100';
            }
        }

        // Call fetchColorData every 1 second (1000 milliseconds)
        setInterval(fetchColorData, 1000);
        
        // Run once on page load
        fetchColorData();
    </script>
</body>
</html>
"""

# --- 4. Main Execution ---
if __name__ == '__main__':
    # Start the ZMQ listener in a background thread
    zmq_thread = threading.Thread(target=zmq_listener, daemon=True)
    zmq_thread.start()
    
    # Start the Flask web server
    # 'host=0.0.0.0' makes it accessible on your network
    print("Flask server starting... Access at http://<your-pi-ip>:5000")
    app.run(host='0.0.0.0', port=5000)


