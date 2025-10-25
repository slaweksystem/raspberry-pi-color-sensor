import flask
from flask import Flask, jsonify
import threading
import zmq
import time
import json

# --- Global variable to store the latest color data ---
# This dictionary will be updated by the ZMQ thread
# and read by the Flask web endpoint.
latest_color_data = {
    "r": 0,
    "g": 0,
    "b": 0,
    "hex": "#000000",
    "dominant": "None"
}
# Keep track of the last time we received data
last_update_time = 0

# --- ZMQ Background Thread ---

def zmq_listener():
    """
    Runs in a background thread.
    Listens for color data from the sensor script via a ZMQ SUB socket.
    """
    global latest_color_data, last_update_time
    
    # Set up the ZMQ socket
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.bind("tcp://*:5556") # Binds to port 5556
    socket.setsockopt_string(zmq.SUBSCRIBE, "") # Subscribe to all messages

    print("[ZMQ] Listener thread started, waiting for data...")

    while True:
        try:
            # Wait for a message
            message = socket.recv_string()
            
            # Parse the JSON message
            data = json.loads(message)
            
            # Update the global variables
            latest_color_data = data
            last_update_time = time.time()
            # print(f"[ZMQ] Received data: {data}") # Uncomment for debugging
            
        except Exception as e:
            print(f"[ZMQ] Error: {e}")
            time.sleep(1)

# --- Flask Web Application ---

app = Flask(__name__)

@app.route('/')
def index():
    """Serves the main HTML page."""
    # All HTML, CSS (via Tailwind), and JS are in this single string.
    return """
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

@app.route('/data')
def data():
    """Provides the latest color data as JSON."""
    global latest_color_data, last_update_time
    
    # Check if the last update was more than 5 seconds ago
    is_receiving = (time.time() - last_update_time) < 5
    
    if is_receiving:
        # If data is recent, send it
        return jsonify({
            'receiving': True,
            'r': latest_color_data.get('r', 0),
            'g': latest_color_data.get('g', 0),
            'b': latest_color_data.get('b', 0),
            'hex': latest_color_data.get('hex', '#000000'),
            'dominant': latest_color_data.get('dominant', 'None')
        })
    else:
        # If data is stale, send a "not receiving" status
        return jsonify({'receiving': False})

# --- Main execution ---

if __name__ == '__main__':
    # Start the ZMQ listener thread
    # It's a 'daemon' thread, so it will exit when the main app exits
    print("[Main] Starting ZMQ listener thread...")
    zmq_thread = threading.Thread(target=zmq_listener, daemon=True)
    zmq_thread.start()
    
    # Start the Flask web server
    # host='0.0.0.0' makes it accessible on your network
    print("[Main] Starting Flask server on http://<your-pi-ip>:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)