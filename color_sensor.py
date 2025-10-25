import RPi.GPIO as GPIO
import time
import zmq  # Re-adding ZeroMQ
import json # Re-adding JSON
import os   # For checking the IPC file

# --- GPIO Pin Definitions (BCM Mode) ---
# These pins are standard for Pi 3B and other 40-pin models
S0 = 5
S1 = 6
S2 = 13
S3 = 19
OUT = 26

# --- Global Calibration Values ---
# These will be set by the calibrate_white_balance() function
# They represent the "white" reading for each channel.
CAL_RED = 1.0
CAL_GREEN = 1.0
CAL_BLUE = 1.0

# --- IPC File Path ---
IPC_PATH = "ipc:///tmp/color_sensor.ipc"

# --- 1. Hardware Setup Function ---
def setup_gpio():
    """Initializes the Raspberry Pi's GPIO pins."""
    print("[Init] Setting up GPIO...")
    GPIO.setmode(GPIO.BCM)
    
    # Setup output pins
    GPIO.setup(S0, GPIO.OUT)
    GPIO.setup(S1, GPIO.OUT)
    GPIO.setup(S2, GPIO.OUT)
    GPIO.setup(S3, GPIO.OUT)
    
    # Setup input pin
    GPIO.setup(OUT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # --- Edge detection removed for simplicity ---
    print("[Init] Using simple polling mode (no edge detection).")
    
    # Set frequency scaling to 20%
    # (Good balance of speed and stability)
    GPIO.output(S0, GPIO.HIGH)
    GPIO.output(S1, GPIO.LOW)
    print("[Init] GPIO setup complete.")

# --- 2. ZeroMQ Setup Function ---
def setup_zeromq():
    """Initializes the ZeroMQ publisher socket using IPC."""
    print("[Init] Setting up ZeroMQ Publisher...")
    
    # Clean up old IPC file if it exists
    ipc_file = IPC_PATH.replace("ipc://", "")
    if os.path.exists(ipc_file):
        print(f"[Init] Removing stale IPC file: {ipc_file}")
        os.remove(ipc_file)
        
    try:
        context = zmq.Context()
        publisher = context.socket(zmq.PUB)
        # Bind to the IPC file path
        publisher.bind(IPC_PATH)
        print(f"[Init] ZMQ Publisher bound to {IPC_PATH}")
        return context, publisher
    except zmq.ZMQError as e:
        print(f"[Init] CRITICAL: Failed to bind ZMQ socket: {e}")
        print(f"[Init] Is another script already using the file {IPC_PATH}?")
        print("[Init] Or check permissions for /tmp/ directory.")
        raise

# --- 3. Raw Sensor Reading Function (Simplified) ---
def get_raw_frequency():
    """
    Reads the raw frequency from the TCS3200 OUT pin
    by manually polling the pin in a loop.
    This avoids GPIO.wait_for_edge() and event detection.
    """
    sample_duration = 0.1 # Sample for 100ms
    pulse_count = 0
    start_time = time.time()
    
    # Get the initial state of the pin
    last_state = GPIO.input(OUT)
    
    while time.time() - start_time < sample_duration:
        current_state = GPIO.input(OUT)
        # Check for a falling edge (HIGH to LOW)
        if last_state == GPIO.HIGH and current_state == GPIO.LOW:
            pulse_count += 1
        last_state = current_state

    # Calculate frequency
    if pulse_count == 0:
        return 0.0
        
    actual_duration = time.time() - start_time
    if actual_duration == 0:
        return 0.0
        
    frequency = pulse_count / actual_duration
    return frequency

# --- 4. Calibration Function ---
def calibrate_white_balance():
    """
    Guides the user to calibrate the sensor for white.
    This is CRITICAL for accurate color representation.
    """
    global CAL_RED, CAL_GREEN, CAL_BLUE
    
    print("\n--- White Balance Calibration ---")
    input("Place a white object (like paper) in front of the sensor and press Enter...")
    
    # Read Red
    GPIO.output(S2, GPIO.LOW)
    GPIO.output(S3, GPIO.LOW)
    time.sleep(0.1) # Give sensor time to settle
    CAL_RED = get_raw_frequency()
    if CAL_RED == 0: CAL_RED = 1.0
    
    # Read Green
    GPIO.output(S2, GPIO.HIGH)
    GPIO.output(S3, GPIO.HIGH)
    time.sleep(0.1)
    CAL_GREEN = get_raw_frequency()
    if CAL_GREEN == 0: CAL_GREEN = 1.0

    # Read Blue
    GPIO.output(S2, GPIO.LOW)
    GPIO.output(S3, GPIO.HIGH)
    time.sleep(0.1)
    CAL_BLUE = get_raw_frequency()
    if CAL_BLUE == 0: CAL_BLUE = 1.0
    
    print("Calibration complete!")
    print(f"  Red Freq: {CAL_RED:.2f}")
    print(f"  Green Freq: {CAL_GREEN:.2f}")
    print(f"  Blue Freq: {CAL_BLUE:.2f}")
    time.sleep(2)

# --- 5. Calibrated Color Reading Function ---
def read_calibrated_color():
    """Reads R, G, and B values and scales them based on calibration."""
    
    # Read Red
    GPIO.output(S2, GPIO.LOW)
    GPIO.output(S3, GPIO.LOW)
    time.sleep(0.1) # Settling time
    raw_r = get_raw_frequency()

    # Read Green
    GPIO.output(S2, GPIO.HIGH)
    GPIO.output(S3, GPIO.HIGH)
    time.sleep(0.1)
    raw_g = get_raw_frequency()

    # Read Blue
    GPIO.output(S2, GPIO.LOW)
    GPIO.output(S3, GPIO.HIGH)
    time.sleep(0.1)
    
    raw_b = get_raw_frequency()
    
    # --- Normalize and Scale ---
    # Apply calibration: (current_reading / white_reading)
    # Then scale to 0-255
    
    r = (raw_r / CAL_RED) * 255.0
    g = (raw_g / CAL_GREEN) * 255.0
    b = (raw_b / CAL_BLUE) * 255.0
    
    # Clamp values to the 0-255 range
    r = int(min(max(r, 0), 255))
    g = int(min(max(g, 0), 255))
    b = int(min(max(b, 0), 255))
    
    return r, g, b

# --- 6. Color Processing Logic (This is the function to edit!) ---
def process_color_data(r, g, b):
    """
    Takes 0-255 RGB values and processes them.
    - Creates a HEX string.
    - Determines the "dominant" color name.
    
    *** This is the function you can easily modify! ***
    """
    
    # 1. Create HEX string
    hex_val = f'#{r:02x}{g:02x}{b:02x}'
    
    # 2. Determine dominant color
    dominant = "Undetermined"
    
    # Simple thresholds for Black, White, and Gray
    if r < 30 and g < 30 and b < 30:
        dominant = "Black"
    elif r > 220 and g > 220 and b > 220:
        dominant = "White"
    # Check if R, G, and B are all close to each other
    elif abs(r - g) < 25 and abs(r - b) < 25 and abs(g - b) < 25:
        dominant = "Gray"
    # Dominant color logic
    elif r > g and r > b:
        dominant = "Red"
    elif g > r and g > b:
        dominant = "Green"
    elif b > r and b > g:
        dominant = "Blue"
    # Add more logic here (e.g., for Yellow, Cyan, Magenta)
    
    # 3. Package data into a dictionary
    data_packet = {
        "r": r,
        "g": g,
        "b": b,
        "hex": hex_val,
        "dominant": dominant,
        "status": "ok" # Add status for the web UI
    }
    
    return data_packet

# --- 7. Main Execution (with ZMQ) ---
def main():
    """Main program loop. Reads sensor and publishes data via ZMQ."""
    
    context = None
    publisher = None
    
    try:
        setup_gpio()
        context, publisher = setup_zeromq()
        calibrate_white_balance()
        
        print("\n--- Starting Sensor Reading and Publishing ---")
        print("Press Ctrl+C to stop.")
        
        while True:
            # 1. Read the color from the sensor
            r, g, b = read_calibrated_color()
            
            # 2. Process the data (get hex, dominant, etc.)
            color_data = process_color_data(r, g, b)
            
            # 3. Convert data packet to JSON string
            message = json.dumps(color_data)
            
            # 4. Publish the message
            publisher.send_string(message)
            
            # 5. Print to console (so we know it's working)
            print(f"Published: R={r}, G={g}, B={b}, Hex={color_data['hex']}, Dominant={color_data['dominant']}")
            
            # 6. Wait a bit before the next reading
            time.sleep(0.1)

    except KeyboardInterrupt:
        # Gracefully exit on Ctrl+C
        print("\nStopping application.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # This ALWAYS runs, ensuring pins and sockets are closed
        if publisher:
            publisher.close()
            print("ZMQ Publisher closed.")
        if context:
            context.term()
            print("ZMQ Context terminated.")
            
        # Clean up the IPC file on exit
        ipc_file = IPC_PATH.replace("ipc://", "")
        if os.path.exists(ipc_file):
            print(f"[Cleanup] Removing IPC file: {ipc_file}")
            os.remove(ipc_file)
            
        GPIO.cleanup()
        print("GPIO cleaned up. Exiting.")

if __name__ == '__main__':
    main()

