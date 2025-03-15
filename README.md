# AIS Data Forwarder

A robust AIS data forwarding solution for Raspberry Pi that reads NMEA data from a serial port (like an AIS receiver) and forwards it to a TCP/IP endpoint.

## Features

- Robust error handling and reconnection logic
- Producer-consumer pattern for efficient data processing
- Configurable serial port and TCP endpoint settings
- Comprehensive logging with rotation
- Runs as a systemd service
- Exponential backoff for connection retries

## Requirements

- Raspberry Pi 4 running Pi OS (Bookworm)
- Python 3.9+
- AIS receiver connected to USB port
- Network connection to forward data

## Installation

### Automatic Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ais-forwarder.git
   cd ais-forwarder
   ```

2. Run the installation script:
   ```bash
   sudo ./install.sh
   ```

3. Edit the configuration file to match your setup:
   ```bash
   sudo nano /home/JLBMaritime/ais-forwarder/config/ais_config.conf
   ```

4. Start the service:
   ```bash
   sudo systemctl start ais-forwarder
   ```

### Manual Installation

1. Create a user for the service:
   ```bash
   sudo useradd -m -s /bin/bash JLBMaritime
   sudo usermod -a -G dialout JLBMaritime
   ```

2. Create the project directory structure:
   ```bash
   sudo mkdir -p /home/JLBMaritime/ais-forwarder/config
   sudo mkdir -p /home/JLBMaritime/ais-forwarder/logs
   ```

3. Copy the files:
   ```bash
   sudo cp ais_forwarder.py /home/JLBMaritime/ais-forwarder/
   sudo cp ais_config.conf /home/JLBMaritime/ais-forwarder/config/
   sudo cp ais-forwarder.service /etc/systemd/system/
   ```

4. Set up a Python virtual environment:
   ```bash
   sudo python3 -m venv /home/JLBMaritime/ais-forwarder/venv
   sudo /home/JLBMaritime/ais-forwarder/venv/bin/pip install pyserial
   ```

5. Set permissions:
   ```bash
   sudo chown -R JLBMaritime:JLBMaritime /home/JLBMaritime/ais-forwarder
   sudo chmod +x /home/JLBMaritime/ais-forwarder/ais_forwarder.py
   ```

6. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable ais-forwarder.service
   sudo systemctl start ais-forwarder
   ```

## Configuration

Edit the configuration file at `/home/JLBMaritime/ais-forwarder/config/ais_config.conf`.

Key configuration options:

```ini
[AIS]
# Serial port where AIS receiver is connected
serial_port = /dev/ttyUSB0
baudrate = 38400

# IP address and port to forward data to
ip = 192.168.1.100
port = 10110

# Logging settings
log_level = INFO
log_file = /home/JLBMaritime/ais-forwarder/logs/ais_forwarder.log
```

## Service Management

Start the service:
```bash
sudo systemctl start ais-forwarder
```

Check service status:
```bash
sudo systemctl status ais-forwarder
```

View logs:
```bash
sudo journalctl -u ais-forwarder -f
```

## Customization

If you need to modify the behavior of the service, you can edit the Python script at `/home/JLBMaritime/ais-forwarder/ais_forwarder.py`. After making changes, restart the service:

```bash
sudo systemctl restart ais-forwarder
```

## Troubleshooting

### Serial Port Issues

If you're having trouble with the serial port:

1. Check that your AIS device is properly connected
2. Verify the serial port path is correct in the config
3. Ensure the JLBMaritime user has permission to access the serial port (is in the dialout group)

### Network Issues

If data isn't being forwarded:

1. Confirm the destination IP and port are correct
2. Check that the destination application is running and listening on the specified port
3. Verify network connectivity between the Raspberry Pi and destination

### Logs

Check the logs for error messages:
```bash
sudo journalctl -u ais-forwarder -f
```

Or check the log file specified in the configuration.

## License

MIT License
