import RPi.GPIO as GPIO
import time
import zmq
import json

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
    
    # Set frequency scaling to 20%
    # (Good balance of speed and stability)
    GPIO.output(S0, GPIO.HIGH)
    GPIO.output(S1, GPIO.LOW)
    print("[Init] GPIO setup complete.")

# --- 2. Raw Sensor Reading Function ---
def get_raw_frequency():
    """
    Reads the raw frequency from the TCS3200 OUT pin.
    This is a blocking function that samples for 0.1 seconds.
    """
    pulse_count = 0
    start_time = time.time()
    sample_duration = 0.1 # Sample for 100ms
    
    while time.time() - start_time < sample_duration:
        # Wait for the pin to go LOW
        GPIO.wait_for_edge(OUT, GPIO.FALLING)
        pulse_count += 1
        
    # Calculate frequency (pulses per second)
    if pulse_count == 0:
        return 0.0 # Avoid division by zero
    
    # We add 1 to pulse_count as a simple way to avoid division by zero
    # and to account for the first pulse
    frequency = pulse_count / sample_duration
    return frequency

# --- 3. Calibration Function ---
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

# --- 4. Calibrated Color Reading Function ---
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

# --- 5. Color Processing Logic (This is the function to edit!) ---
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
        "dominant": dominant
    }
    
    return data_packet

# --- 6. Main Execution ---
def main():
    """Main program loop."""
    
    setup_gpio()
    calibrate_white_balance()
    
    # --- ZMQ Publisher Setup ---
    print("[Init] Setting up ZMQ Publisher...")
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    # Connect to the address the server is BINDING to.
    # If on the same Pi, 'localhost' is perfect.
    socket.connect("tcp://localhost:5556")
    print("[Init] ZMQ Publisher connected. Starting sensor loop.")
    
    while True:
        # 1. Read the color from the sensor
        r, g, b = read_calibrated_color()
        
        # 2. Process the data (get hex, dominant, etc.)
        color_data = process_color_data(r, g, b)
        
        # 3. Convert data to a JSON string
        message = json.dumps(color_data)
        
        # 4. Publish the message
        socket.send_string(message)
        
        # 5. Print to console for local debugging
        print(f"Sent: R={r}, G={g}, B={b}, Hex={color_data['hex']}, Dom={color_data['dominant']}")
        
        # 6. Wait a bit before the next reading
        time.sleep(0.5) # Send data twice per second

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # Gracefully exit on Ctrl+C
        print("\nStopping application.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # This ALWAYS runs, ensuring pins are reset
        GPIO.cleanup()
        print("GPIO cleaned up. Exiting.")
