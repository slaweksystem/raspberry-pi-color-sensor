#!/usr/bin/python3
import zmq
import json
import time
from flask import Flask, render_template_string, jsonify, request
from threading import Thread, Lock

# --- ZMQ Socket Definitions ---
IPC_FILE = "ipc:///tmp/color_sensor.ipc"

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Global State for Caching ---
# This dictionary will hold the last known color data
latest_color_data = {
    "r": 0, "g": 0, "b": 0,
    "hex": "#000000",
    "dominant": "---",
    "receiving": False,
    "last_seen": 0.0
}
# A lock to ensure thread-safe access to the global data
data_lock = Lock()

# --- ZMQ Background Thread ---

def zmq_data_fetcher():
    """
    A background thread that continuously polls the sensor script
    for the latest data and caches it.
    """
    global latest_color_data
    context = zmq.Context()
    socket = context.socket(zmq.REQ) # REQ (Request) socket
    
    print("[ZMQ] Connecting REQ socket to sensor at {}...".format(IPC_FILE))
    socket.connect(IPC_FILE)
    print("[ZMQ] Socket connected.")
    
    while True:
        try:
            # 1. Send a request for data
            socket.send_string("GET_DATA")
            
            # 2. Wait for a reply, but with a timeout
            if socket.poll(timeout=1000): # 1 second timeout
                # We got a reply!
                data = socket.recv_json()
                
                with data_lock:
                    latest_color_data.update(data)
                    latest_color_data["receiving"] = True
                    latest_color_data["last_seen"] = time.time()
            else:
                # Timeout! We didn't get a reply.
                print("[ZMQ] Timeout: No data received from sensor script.")
                with data_lock:
                    latest_color_data["receiving"] = False

        except zmq.ZMQError as e:
            print(f"[ZMQ] Error: {e}. Retrying connection...")
            with data_lock:
                latest_color_data["receiving"] = False
            # Recreate socket on error
            socket.close()
            socket = context.socket(zmq.REQ)
            socket.connect(IPC_FILE)
            time.sleep(2) # Wait before retrying
        except Exception as e:
            print(f"[ZMQ] Unknown error in fetcher thread: {e}")
            with data_lock:
                latest_color_data["receiving"] = False
            time.sleep(2)
        
        # Poll rate
        time.sleep(0.5) # Request new data twice per second

# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    # We use render_template_string to keep everything in one file
    return render_template_string(HTML_TEMPLATE)

@app.route('/data')
def data():
    """Provides the latest color data as JSON for the webpage to fetch."""
    with data_lock:
        # Check if the last_seen timestamp is too old
        if (time.time() - latest_color_data["last_seen"]) > 2.0:
            latest_color_data["receiving"] = False
        
        # Return a copy of the data
        return jsonify(latest_color_data.copy())

@app.route('/calibrate', methods=['POST'])
def calibrate():
    """
    Receives the 'calibrate' request from the webpage
    and sends the command to the sensor script.
    """
    print("[API] Received /calibrate request from UI.")
    
    # We need a *new* socket for this command
    # as the main fetcher socket is busy in its REQ/REP loop
    context = zmq.Context.instance() # Get global instance
    cmd_socket = context.socket(zmq.REQ)
    cmd_socket.connect(IPC_FILE)
    
    try:
        # Send the calibrate command
        cmd_socket.send_string("CALIBRATE")
        
        # Wait for a simple "ok" reply with a timeout
        if cmd_socket.poll(timeout=1000):
            reply = cmd_socket.recv_json()
            print(f"[ZMQ] Received calibration reply: {reply}")
            return jsonify({"status": "ok", "message": "Calibration requested", "reply": reply})
        else:
            print("[ZMQ] Calibration request timed out.")
            return jsonify({"status": "error", "message": "Calibration request timed out"}), 504
            
    except Exception as e:
        print(f"[API] Error sending calibrate command: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cmd_socket.close()


# --- HTML Template ---
# This is the exact same "old" GUI you liked, with the calibrate button added.
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
        /* Style for the calibrate button */
        #calibrate-btn {
            transition: background-color 0.2s ease, transform 0.2s ease;
        }
        #calibrate-btn:active {
            transform: scale(0.95);
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
        <div id="status-container" class="p-3 rounded-lg mb-6">
            <p id="status-text" class="text-lg font-semibold">Status: Connecting...</p>
        </div>

        <!-- Calibrate Button -->
        <button id="calibrate-btn" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg shadow-lg">
            Calibrate White Balance
        </button>
        <p id="calibrate-status" class="text-sm text-gray-400 mt-2 h-4"></p>

    </div>

    <script>
        // This script will run in the browser
        
        const colorBox = document.getElementById('color-box');
        const rgbValues = document.getElementById('rgb-values');
        const dominantColor = document.getElementById('dominant-color');
        const statusContainer = document.getElementById('status-container');
        const statusText = document.getElementById('status-text');
        const calibrateBtn = document.getElementById('calibrate-btn');
        const calibrateStatus = document.getElementById('calibrate-status');

        // Function to fetch data from our Flask server
        async function fetchColorData() {
            try {
                // Fetch data from the /data endpoint
                const response = await fetch('/data');
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const data = await response.json();

                if (data.receiving) {
                    // We are receiving data!
                    colorBox.style.backgroundColor = data.hex;
                    rgbValues.textContent = `R: ${data.r} G: ${data.g} B: ${data.b}`;
                    dominantColor.textContent = `Dominant: ${data.dominant}`;
                    
                    statusText.textContent = 'Status: Receiving Data';
                    statusContainer.className = 'p-3 rounded-lg mb-6 bg-green-700 text-green-100';

                } else {
                    // We are not receiving data
                    statusText.textContent = 'Status: Not Receiving Data';
                    statusContainer.className = 'p-3 rounded-lg mb-6 bg-red-700 text-red-100';
                }

            } catch (error) {
                // An error occurred (e.g., server is down)
                console.error('Fetch error:', error);
                statusText.textContent = 'Status: Server Unreachable';
                statusContainer.className = 'p-3 rounded-lg mb-6 bg-red-700 text-red-100';
            }
        }

        // Function to handle calibration
        async function handleCalibrate() {
            calibrateStatus.textContent = 'Calibrating... (Point at white object)';
            calibrateBtn.disabled = true;
            calibrateBtn.classList.add('opacity-50');

            try {
                const response = await fetch('/calibrate', {
                    method: 'POST',
                });
                
                const result = await response.json();

                if (response.ok) {
                    calibrateStatus.textContent = 'Calibration complete!';
                } else {
                    calibrateStatus.textContent = `Error: ${result.message}`;
                }

            } catch (error) {
                console.error('Calibrate error:', error);
                calibrateStatus.textContent = 'Error: Failed to send request.';
            }

            // Re-enable button and clear status after a moment
            setTimeout(() => {
                calibrateStatus.textContent = '';
                calibrateBtn.disabled = false;
                calibrateBtn.classList.remove('opacity-50');
            }, 3000);
        }

        // Add event listener to the button
        calibrateBtn.addEventListener('click', handleCalibrate);

        // Call fetchColorData every 1 second (1000 milliseconds)
        setInterval(fetchColorData, 1000);
        
        // Run once on page load
        fetchColorData();
    </script>
</body>
</html>
"""

# --- Main Execution ---

if __name__ == '__main__':
    # Start the ZMQ data fetcher thread
    print("[Init] Starting ZMQ data fetcher thread...")
    fetcher_thread = Thread(target=zmq_data_fetcher, daemon=True)
    fetcher_thread.start()
    
    # Start the Flask web server
    print("[Init] Starting Flask web server on http://0.0.0.0:5000")
    # We use 0.0.0.0 to make it accessible on the network
    app.run(host='0.0.0.0', port=5000)

