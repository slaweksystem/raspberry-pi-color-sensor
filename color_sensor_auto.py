#!/usr/bin/python3
import RPi.GPIO as GPIO
import time
import zmq
import json
import os # For checking file path

# --- GPIO Pin Definitions (BCM Mode) ---
S2 = 13
S3 = 19
OUT = 26

# --- Global State ---
CALIBRATION_VALUES = {
    'R': 1.0,
    'G': 1.0,
    'B': 1.0
}
CALIBRATION_FILE = 'calibration.json'

# --- ZMQ Socket Definitions ---
IPC_FILE = "ipc:///tmp/color_sensor.ipc"
IPC_SOCKET_PATH = "/tmp/color_sensor.ipc"

def setup_gpio():
    """Sets up the GPIO pins."""
    print("[Init] Setting up GPIO...")
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(S2, GPIO.OUT)
    GPIO.setup(S3, GPIO.OUT)
    GPIO.setup(OUT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("[Init] GPIO setup complete.")

def load_calibration():
    """Loads calibration values from the JSON file."""
    global CALIBRATION_VALUES
    try:
        with open(CALIBRATION_FILE, 'r') as f:
            CALIBRATION_VALUES = json.load(f)
        print(f"[Init] Loaded calibration data: {CALIBRATION_VALUES}")
    except FileNotFoundError:
        print("[Init] No calibration file found. Using default values.")
        save_calibration() # Save the defaults
    except Exception as e:
        print(f"[Init] Error loading calibration file: {e}. Using defaults.")

def save_calibration():
    """Saves the current calibration values to the JSON file."""
    try:
        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(CALIBRATION_VALUES, f, indent=4)
        print(f"[Action] Saved new calibration data: {CALIBRATION_VALUES}")
    except Exception as e:
        print(f"[Error] Failed to save calibration file: {e}")

def get_raw_frequency():
    """Measures the frequency from the OUT pin using simple polling."""
    start_time = time.monotonic()
    pulse_count = 0
    
    while GPIO.input(OUT) == GPIO.HIGH and time.monotonic() - start_time < 0.1:
        pass 
    while GPIO.input(OUT) == GPIO.LOW and time.monotonic() - start_time < 0.1:
        pass 
    
    start_time = time.monotonic() 
    end_time = start_time + 0.1 
    
    last_state = GPIO.input(OUT)
    
    while time.monotonic() < end_time:
        current_state = GPIO.input(OUT)
        if current_state == GPIO.LOW and last_state == GPIO.HIGH:
            pulse_count += 1
        last_state = current_state
        
    duration = time.monotonic() - start_time
    if duration == 0:
        return 0
        
    return pulse_count / duration 

def set_filter_color(color):
    """Sets the S2 and S3 pins to select the desired color filter."""
    if color == 'R':
        GPIO.output(S2, GPIO.LOW)
        GPIO.output(S3, GPIO.LOW)
    elif color == 'G':
        GPIO.output(S2, GPIO.HIGH)
        GPIO.output(S3, GPIO.HIGH)
    elif color == 'B':
        GPIO.output(S2, GPIO.LOW)
        GPIO.output(S3, GPIO.HIGH)
    elif color == 'C': 
        GPIO.output(S2, GPIO.HIGH)
        GPIO.output(S3, GPIO.LOW)
    time.sleep(0.01)

def perform_calibration():
    """
    Performs the white balance calibration.
    This is called when the 'CALIBRATE' command is received.
    """
    global CALIBRATION_VALUES
    print("[Action] Starting white balance calibration...")
    
    set_filter_color('R')
    CALIBRATION_VALUES['R'] = get_raw_frequency()
    if CALIBRATION_VALUES['R'] == 0: CALIBRATION_VALUES['R'] = 1.0 
    
    set_filter_color('G')
    CALIBRATION_VALUES['G'] = get_raw_frequency()
    if CALIBRATION_VALUES['G'] == 0: CALIBRATION_VALUES['G'] = 1.0
    
    set_filter_color('B')
    CALIBRATION_VALUES['B'] = get_raw_frequency()
    if CALIBRATION_VALUES['B'] == 0: CALIBRATION_VALUES['B'] = 1.0
    
    print("[Action] Calibration complete.")
    save_calibration()

def process_color_data(r, g, b):
    """
    Processes the raw RGB values into a hex code and dominant color.
    """
    if r > g and r > b:
        dominant = 'Red 🔴'
    elif g > r and g > b:
        dominant = 'Green 🟢'
    elif b > r and b > g:
        dominant = 'Blue 🔵'
    elif abs(r - g) < 20 and abs(g - b) < 20:
        if r > 200:
            dominant = 'White ⚪'
        elif r < 50:
            dominant = 'Black ⚫'
        else:
            dominant = 'Grey 🔘'
    else:
        dominant = '---'

    hex_code = f"#{r:02x}{g:02x}{b:02x}"
    
    return hex_code, dominant

def get_calibrated_color():
    """Reads all three color filters and returns calibrated RGB values."""
    set_filter_color('R')
    raw_r = get_raw_frequency()
    r = int((raw_r / CALIBRATION_VALUES['R']) * 255)
    
    set_filter_color('G')
    raw_g = get_raw_frequency()
    g = int((raw_g / CALIBRATION_VALUES['G']) * 255)
    
    set_filter_color('B')
    raw_b = get_raw_frequency()
    b = int((raw_b / CALIBRATION_VALUES['B']) * 255)
    
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    
    return r, g, b

def cleanup_ipc_file():
    """Remove the stale IPC socket file if it exists."""
    if os.path.exists(IPC_SOCKET_PATH):
        print(f"[Init] Removing stale IPC socket file: {IPC_SOCKET_PATH}")
        try:
            os.remove(IPC_SOCKET_PATH)
        except OSError as e:
            print(f"[Error] Could not remove IPC file: {e}. Please remove it manually.")
            print("Try: 'sudo rm /tmp/color_sensor.ipc'")

def main():
    """Main loop: listens for requests, reads sensor, and replies."""
    context = zmq.Context()
    socket = context.socket(zmq.REP) # REP (Reply) socket
    
    try:
        cleanup_ipc_file() # Clean up before binding
        print("[Init] Setting up ZMQ REP socket...")
        socket.bind(IPC_FILE)
        print(f"[Init] ZMQ socket bound to {IPC_FILE}")
        
        setup_gpio()
        load_calibration()
        
        print("[Init] Starting main loop. Waiting for requests... Press Ctrl+C to exit.")
        
        while True:
            # Wait for any request from the web server
            message = socket.recv_string()
            
            if message == "GET_DATA":
                # 1. Read the calibrated color
                r, g, b = get_calibrated_color()
                
                # 2. Process the data
                hex_code, dominant = process_color_data(r, g, b)
                
                # 3. Create the data payload
                data = {
                    'r': r,
                    'g': g,
                    'b': b,
                    'hex': hex_code,
                    'dominant': dominant
                }
                
                # 4. Send the data back
                socket.send_json(data)
                
            elif message == "CALIBRATE":
                print("[ZMQ] Received CALIBRATE command.")
                perform_calibration()
                # Send a simple "ok" reply
                socket.send_json({"status": "calibration_complete"})

    except KeyboardInterrupt:
        print("\nMeasurement stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Cleaning up...")
        socket.close()
        context.term()
        GPIO.cleanup()
        cleanup_ipc_file() # Clean up after stopping
        print("GPIO cleaned up. Exiting.")

if __name__ == '__main__':
    main()

