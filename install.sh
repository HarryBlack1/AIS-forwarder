#!/bin/bash
# AIS Forwarder Installation Script
# For Raspberry Pi OS (Bookworm)

# Exit on any error
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

echo "==== AIS Forwarder Installation Script ===="
echo "This script will install the AIS Forwarder service on your Raspberry Pi."
echo "Host: AIS"
echo "User: JLBMaritime"
echo

# Create user if it doesn't exist
if ! id -u JLBMaritime &>/dev/null; then
  echo "Creating user JLBMaritime..."
  useradd -m -s /bin/bash JLBMaritime
  # Add to dialout group for serial port access
  usermod -a -G dialout JLBMaritime
fi

# Install dependencies
echo "Installing dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv

# Create project directories
echo "Creating project directories..."
mkdir -p /home/JLBMaritime/ais-forwarder/config
mkdir -p /home/JLBMaritime/ais-forwarder/logs

# Copy files
echo "Copying project files..."
cp ais_forwarder.py /home/JLBMaritime/ais-forwarder/
cp ais_config.conf /home/JLBMaritime/ais-forwarder/config/

# Create virtual environment and install requirements
echo "Setting up Python environment..."
python3 -m venv /home/JLBMaritime/ais-forwarder/venv
/home/JLBMaritime/ais-forwarder/venv/bin/pip install pyserial

# Fix permissions
echo "Setting file permissions..."
chown -R JLBMaritime:JLBMaritime /home/JLBMaritime/ais-forwarder
chmod +x /home/JLBMaritime/ais-forwarder/ais_forwarder.py

# Install service
echo "Installing systemd service..."
cp ais-forwarder.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable ais-forwarder.service

echo
echo "Installation complete!"
echo
echo "To start the service:"
echo "  sudo systemctl start ais-forwarder"
echo
echo "To check service status:"
echo "  sudo systemctl status ais-forwarder"
echo
echo "To view logs:"
echo "  sudo journalctl -u ais-forwarder -f"
echo
echo "Service configuration file is at:"
echo "  /home/JLBMaritime/ais-forwarder/config/ais_config.conf"
echo
echo "You may need to edit the configuration to match your setup."
echo "Particularly the serial port and TCP endpoint IP/port."
