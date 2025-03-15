#!/usr/bin/env python3
"""
AIS Data Forwarding Script
--------------------------
This script reads AIS data from a serial port and forwards it to a TCP endpoint.
It includes robust error handling, connection management, and configuration options.

Usage:
    python3 ais_forwarder.py [config_file_path]
"""

import serial
import socket
import threading
import configparser
import time
import logging
import sys
import signal
import queue
from typing import Dict, Optional, Union, List, Tuple
from dataclasses import dataclass
import os
from logging.handlers import RotatingFileHandler

# Constants
DEFAULT_CONFIG_PATH = "/home/JLBMaritime/ais-forwarder/config/ais_config.conf"
MAX_QUEUE_SIZE = 1000
SOCKET_TIMEOUT = 5  # seconds
RECONNECT_DELAY = 5  # seconds
BACKOFF_FACTOR = 1.5  # for exponential backoff
MAX_BACKOFF_DELAY = 60  # maximum seconds to wait between retries

# Define a dataclass for holding configuration details
@dataclass
class AISConfig:
    """Configuration data for AIS connection."""
    serial_port: str
    ip: str
    port: int
    baudrate: int = 38400
    serial_timeout: float = 2.0
    max_retries: int = 3
    log_level: str = "INFO"
    log_file: Optional[str] = None
    log_max_size: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5


# Configure logging
def setup_logging(config: AISConfig) -> None:
    """Set up logging with optional file handler based on configuration."""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    
    # Create handlers
    handlers = []
    
    # Always add a console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # Add file handler if specified
    if config.log_file:
        try:
            # Ensure directory exists
            log_dir = os.path.dirname(config.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            file_handler = RotatingFileHandler(
                config.log_file,
                maxBytes=config.log_max_size,
                backupCount=config.log_backup_count
            )
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except Exception as e:
            print(f"Error setting up log file: {e}")
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )


# Load configuration from .conf file
def load_config(file_path: str) -> AISConfig:
    """
    Load and validate configuration from file.
    
    Args:
        file_path: Path to the configuration file
        
    Returns:
        AISConfig object with validated parameters
        
    Raises:
        SystemExit: If configuration is invalid or file can't be read
    """
    config = configparser.ConfigParser()
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        config.read(file_path)
        
        if not config.has_section("AIS"):
            raise ValueError("Missing 'AIS' section in config file")
        
        required_fields = ["serial_port", "ip", "port"]
        for field in required_fields:
            if not config.has_option("AIS", field):
                raise ValueError(f"Missing required field '{field}' in AIS section")
        
        # Create AISConfig with defaults
        ais_config = AISConfig(
            serial_port=config["AIS"]["serial_port"],
            ip=config["AIS"]["ip"],
            port=int(config["AIS"]["port"]),
            baudrate=config.getint("AIS", "baudrate", fallback=38400),
            serial_timeout=config.getfloat("AIS", "serial_timeout", fallback=2.0),
            max_retries=config.getint("AIS", "max_retries", fallback=3),
            log_level=config.get("AIS", "log_level", fallback="INFO"),
            log_file=config.get("AIS", "log_file", fallback=None),
            log_max_size=config.getint("AIS", "log_max_size", fallback=10 * 1024 * 1024),
            log_backup_count=config.getint("AIS", "log_backup_count", fallback=5)
        )
        
        return ais_config
    except Exception as e:
        logging.error(f"Error loading config file: {e}")
        sys.exit(1)


class SocketManager:
    """Manages TCP socket connections with connection pooling and reconnection logic."""
    
    def __init__(self, host: str, port: int, max_retries: int = 3):
        self.host = host
        self.port = port
        self.max_retries = max_retries
        self.socket = None
        self.socket_lock = threading.Lock()
        self.connected = False
        self.last_attempt = 0
        self.backoff_delay = RECONNECT_DELAY
    
    def connect(self) -> bool:
        """
        Establish connection to the socket.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        with self.socket_lock:
            if self.connected:
                return True
            
            # Implement exponential backoff
            current_time = time.time()
            time_since_last_attempt = current_time - self.last_attempt
            
            if time_since_last_attempt < self.backoff_delay:
                # Not enough time has passed since last attempt
                return False
            
            self.last_attempt = current_time
            
            try:
                if self.socket:
                    self.socket.close()
                
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(SOCKET_TIMEOUT)
                self.socket.connect((self.host, self.port))
                self.connected = True
                # Reset backoff on successful connection
                self.backoff_delay = RECONNECT_DELAY
                logging.info(f"Connected to {self.host}:{self.port}")
                return True
            except socket.error as e:
                logging.warning(f"Failed to connect to {self.host}:{self.port}: {e}")
                # Increase backoff delay for next attempt (with max limit)
                self.backoff_delay = min(self.backoff_delay * BACKOFF_FACTOR, MAX_BACKOFF_DELAY)
                self.connected = False
                return False
    
    def send(self, data: bytes) -> bool:
        """
        Send data through the socket.
        
        Args:
            data: Bytes to send
            
        Returns:
            bool: True if send successful, False otherwise
        """
        with self.socket_lock:
            if not self.connected and not self.connect():
                return False
            
            try:
                self.socket.sendall(data)
                return True
            except socket.error as e:
                logging.warning(f"Error sending data to {self.host}:{self.port}: {e}")
                self.connected = False
                return False
    
    def close(self) -> None:
        """Close the socket connection."""
        with self.socket_lock:
            if self.socket:
                try:
                    self.socket.close()
                except Exception as e:
                    logging.warning(f"Error closing socket: {e}")
                finally:
                    self.connected = False
                    self.socket = None


class AISHandler:
    """Handles AIS data processing with producer-consumer pattern."""
    
    def __init__(self, config: AISConfig):
        self.config = config
        self.serial_port = None
        self.data_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self.socket_manager = SocketManager(
            config.ip, 
            config.port, 
            config.max_retries
        )
        self.running = False
        self.producer_thread = None
        self.consumer_thread = None
    
    def _producer(self) -> None:
        """Read data from serial port and add to queue."""
        while self.running:
            try:
                if self.serial_port is None or not self.serial_port.is_open:
                    self._connect_serial()
                    if self.serial_port is None:
                        time.sleep(RECONNECT_DELAY)
                        continue
                
                line = self.serial_port.readline()
                if line:
                    logging.debug(f"Received AIS data: {line}")
                    try:
                        self.data_queue.put(line, block=True, timeout=1)
                    except queue.Full:
                        logging.warning("Queue full, dropping AIS data")
            except serial.SerialException as e:
                logging.error(f"AIS serial read error: {e}")
                self._close_serial()
                time.sleep(RECONNECT_DELAY)
            except Exception as e:
                logging.error(f"Unexpected error in producer: {e}")
                time.sleep(1)
    
    def _consumer(self) -> None:
        """Process data from queue and send to TCP endpoint."""
        while self.running:
            try:
                # Get data with timeout to allow checking self.running periodically
                try:
                    data = self.data_queue.get(block=True, timeout=1)
                except queue.Empty:
                    continue
                
                sent = self.socket_manager.send(data)
                if sent:
                    logging.debug(f"Sent {len(data)} bytes to {self.config.ip}:{self.config.port}")
                else:
                    logging.warning("Failed to send data, re-queuing")
                    try:
                        # Try to put it back in the queue
                        self.data_queue.put(data, block=False)
                    except queue.Full:
                        logging.warning("Queue full, dropping data on send failure")
                
                self.data_queue.task_done()
            except Exception as e:
                logging.error(f"Unexpected error in consumer: {e}")
                time.sleep(1)
    
    def _connect_serial(self) -> None:
        """Connect to the serial port."""
        try:
            self.serial_port = serial.Serial(
                self.config.serial_port,
                baudrate=self.config.baudrate,
                timeout=self.config.serial_timeout
            )
            logging.info(f"Connected to AIS serial port: {self.config.serial_port}")
        except serial.SerialException as e:
            logging.error(f"Failed to connect to serial port {self.config.serial_port}: {e}")
            self.serial_port = None
    
    def _close_serial(self) -> None:
        """Close the serial port connection."""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception as e:
                logging.warning(f"Error closing serial port: {e}")
            finally:
                self.serial_port = None
    
    def start(self) -> None:
        """Start the AIS handler threads."""
        if self.running:
            return
        
        self.running = True
        
        # Start producer thread
        self.producer_thread = threading.Thread(
            target=self._producer,
            name="AIS-Producer",
            daemon=True
        )
        self.producer_thread.start()
        
        # Start consumer thread
        self.consumer_thread = threading.Thread(
            target=self._consumer,
            name="AIS-Consumer", 
            daemon=True
        )
        self.consumer_thread.start()
        
        logging.info("AIS handler started")
    
    def stop(self) -> None:
        """Stop the AIS handler threads."""
        if not self.running:
            return
        
        logging.info("Stopping AIS handler...")
        self.running = False
        
        # Wait for threads to terminate (with timeout)
        if self.producer_thread and self.producer_thread.is_alive():
            self.producer_thread.join(timeout=5)
        
        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join(timeout=5)
        
        # Close connections
        self._close_serial()
        self.socket_manager.close()
        
        logging.info("AIS handler stopped")


class Application:
    """Main application class."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.ais_handler = None
        self.running = False
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame) -> None:
        """Handle termination signals."""
        logging.info(f"Received signal {sig}, shutting down...")
        self.stop()
    
    def start(self) -> None:
        """Start the application."""
        try:
            # Load configuration
            config = load_config(self.config_path)
            
            # Setup logging
            setup_logging(config)
            
            logging.info(f"Starting AIS forwarding from {config.serial_port} to {config.ip}:{config.port}")
            
            # Create and start AIS handler
            self.ais_handler = AISHandler(config)
            self.ais_handler.start()
            
            self.running = True
            
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            logging.error(f"Error in application: {e}")
            self.stop()
    
    def stop(self) -> None:
        """Stop the application."""
        self.running = False
        
        if self.ais_handler:
            self.ais_handler.stop()
        
        logging.info("Application stopped")
        sys.exit(0)


def main():
    """Main entry point for the application."""
    # Allow configuration file path to be passed as a command-line argument
    config_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    
    app = Application(config_file)
    app.start()


if __name__ == "__main__":
    main()
