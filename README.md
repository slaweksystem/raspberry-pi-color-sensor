# Raspberry Pi TCS3200 Color Sensor with Web Interface

A simple project to test and use the TCS3200 color sensor on a Raspberry Pi 3. It provides both a command-line output and a simple HTTP web interface to display the detected color in real-time.

-----

## 📋 Overview

This project is designed as a straightforward way to interface the popular **TCS3200 color sensor** with a Raspberry Pi. The core functionality is written in Python and uses the `RPi.GPIO` library. The included web interface, built with **Flask**, allows you to view the sensor's readings remotely from any device on the same network.

### ✨ Features

  * **Reads RGB values** from the TCS3200 sensor.
  * **Simple Color Detection** logic to identify the dominant color (Red, Green, or Blue).
  * **White Balance Calibration** function to adapt to ambient lighting.
  * **HTTP Web Interface** to display the currently detected color and its RGB values.
  * Tested on a **Raspberry Pi 3**, but should be compatible with other models.

-----

## 🛠️ Hardware Requirements

  * Raspberry Pi 3 (or any model with GPIO pins)
  * TCS3200 Color Sensor Module
  * Female-to-Female Jumper Wires

### 🔌 Wiring Diagram

Connect the TCS3200 sensor to the Raspberry Pi's GPIO pins as follows:

| TCS3200 Pin | Raspberry Pi Pin (BCM) | Purpose                  |
|-------------|--------------------------|--------------------------|
| **VCC** | 5V                       | Power                    |
| **GND** | GND                      | Ground                   |
| **S0** | GPIO 5                   | Frequency Scaling Control |
| **S1** | GPIO 6                   | Frequency Scaling Control |
| **S2** | GPIO 13                  | Photodiode Type Select   |
| **S3** | GPIO 19                  | Photodiode Type Select   |
| **OUT** | GPIO 26                  | Frequency Output         |

-----

## 🚀 Getting Started

### 1\. Clone the Repository

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

### 2\. Install Dependencies

This project requires `RPi.GPIO` and `Flask`. Install them using pip:

```bash
pip install -r requirements.txt
```

*(If you don't have a `requirements.txt` file, you can create one with `Flask` and `RPi.GPIO` or install them directly: `pip install Flask RPi.GPIO`)*

### 3\. Run the Application

Execute the main Python script with `sudo` permissions to access the GPIO pins.

```bash
sudo python3 app.py
```

### 4\. Calibrate the Sensor

The script will first ask you to perform a **white balance calibration**.

  * Place a white object (like a piece of paper) in front of the sensor.
  * Press **Enter** in the terminal to complete the calibration.
  * The web server will then start.

### 5\. Access the Web Interface

Open a web browser on a device connected to the same network as your Raspberry Pi and navigate to:

`http://<your-pi-ip-address>:5000`

You should see a simple webpage displaying the color detected by the sensor. The page will update automatically.

-----

## 📝 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
