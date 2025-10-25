#!/bin/bash

# This script creates and enables two systemd services:
# 1. pi_color_web.service: Runs the Flask web server (as user 'slawek').
# 2. pi_color_sensor.service: Runs the color sensor script (as user 'root' for GPIO).

# --- Configuration ---
PROJECT_DIR="/home/slawek/Projects/raspberry-pi-color-sensor"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python3"
WEB_USER="slawek"
SENSOR_USER="slawek" # Sensor needs root for GPIO access

WEB_SCRIPT_NAME="web_server_auto.py"
SENSOR_SCRIPT_NAME="color_sensor_auto.py"

WEB_SERVICE_NAME="pi_color_web.service"
SENSOR_SERVICE_NAME="pi_color_sensor.service"

WEB_SERVICE_FILE_PATH="/etc/systemd/system/${WEB_SERVICE_NAME}"
SENSOR_SERVICE_FILE_PATH="/etc/systemd/system/${SENSOR_SERVICE_NAME}"

# --- Check for root ---
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root. Please use 'sudo ./setup_web_service.sh'"
  exit 1
fi

echo "Setting up services for Pi Color Sensor..."

# --- 1. Create Web Server Service File ---
echo "Creating ${WEB_SERVICE_NAME}..."
cat << EOF > ${WEB_SERVICE_FILE_PATH}
[Unit]
Description=Pi Color Sensor Web Server
After=network.target

[Service]
User=${WEB_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} ${PROJECT_DIR}/${WEB_SCRIPT_NAME}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# --- 2. Create Color Sensor Service File ---
echo "Creating ${SENSOR_SERVICE_NAME}..."
cat << EOF > ${SENSOR_SERVICE_FILE_PATH}
[Unit]
Description=Pi Color Sensor Reader Process
After=network.target
# We can make the web service depend on this sensor service
Wants=${WEB_SERVICE_NAME}

[Service]
User=${SENSOR_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} ${PROJECT_DIR}/${SENSOR_SCRIPT_NAME}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# --- 3. Reload, Enable, and Start Services ---
echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling both services to start on boot..."
systemctl enable ${WEB_SERVICE_NAME}
systemctl enable ${SENSOR_SERVICE_NAME}

echo "Restarting services..."
systemctl restart ${WEB_SERVICE_NAME}
systemctl restart ${SENSOR_SERVICE_NAME}

echo "Done!"
echo
echo "--- Status for Web Server (${WEB_SERVICE_NAME}) ---"
systemctl status ${WEB_SERVICE_NAME} --no-pager
echo
echo "--- Status for Sensor (${SENSOR_SERVICE_NAME}) ---"
systemctl status ${SENSOR_SERVICE_NAME} --no-pager