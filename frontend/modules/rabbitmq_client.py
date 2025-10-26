import pika
import json
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker

class RabbitMQClient(QObject):
    """Thread-safe RabbitMQ client using QTimer for event processing"""
    
    connection_status_changed = pyqtSignal(bool)
    message_received = pyqtSignal(dict)
    
    def __init__(self, host='localhost', port=5672, username='guest', password='guest'):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        
        self.connection = None
        self.channel = None
        self.is_connected = False
        self.mutex = QMutex()
        
        self.command_queue = 'greenhouse_commands'
        self.response_queue = 'command_responses'
        
        self.pending_messages = []
        self.consuming = False
        
        # Setup periodic timer for connection maintenance
        self.maintenance_timer = QTimer()
        self.maintenance_timer.timeout.connect(self._process_events)
        self.maintenance_timer.start(100)  # Process every 100ms
        
        self.logger = logging.getLogger('RabbitMQClient')
        
    def connect(self):
        """Establish connection to RabbitMQ server"""
        with QMutexLocker(self.mutex):
            try:
                if self.connection and not self.connection.is_closed:
                    self.connection.close()
                
                credentials = pika.PlainCredentials(self.username, self.password)
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300,
                    # Add these parameters for better stability
                    socket_timeout=5,
                    retry_delay=5,
                    connection_attempts=3
                )
                
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                # Declare queues
                self.channel.queue_declare(queue=self.command_queue, durable=True)
                self.channel.queue_declare(queue=self.response_queue, durable=True)
                
                self.is_connected = True
                self.logger.info("Successfully connected to RabbitMQ")
                self.connection_status_changed.emit(True)
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to connect to RabbitMQ: {e}")
                self.is_connected = False
                self.connection_status_changed.emit(False)
                return False
    
    def disconnect(self):
        """Close RabbitMQ connection"""
        with QMutexLocker(self.mutex):
            self.consuming = False
            try:
                if self.connection and not self.connection.is_closed:
                    self.connection.close()
                self.is_connected = False
                self.connection_status_changed.emit(False)
                self.logger.info("Disconnected from RabbitMQ")
            except Exception as e:
                self.logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    def send_message(self, queue_name, message):
        """Send message to specified queue - thread safe"""
        with QMutexLocker(self.mutex):
            if not self.is_connected:
                self.logger.warning("Cannot send message: Not connected to RabbitMQ")
                return False
                
            try:
                self.channel.basic_publish(
                    exchange='',
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json'
                    )
                )
                self.logger.debug(f"Message sent to queue '{queue_name}': {message}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to send message to queue '{queue_name}': {e}")
                self.is_connected = False
                self.connection_status_changed.emit(False)
                return False
    
    def send_command(self, command_data):
        """Send command to greenhouse commands queue"""
        return self.send_message(self.command_queue, command_data)
    
    def start_consuming(self):
        """Start consuming messages using non-blocking approach"""
        if not self.is_connected:
            return False
            
        self.consuming = True
        self.logger.info("Started message consumption")
        return True
    
    def _process_events(self):
        """Process RabbitMQ events and check for new messages"""
        if not self.is_connected or not self.consuming:
            return
            
        with QMutexLocker(self.mutex):
            try:
                # Check for messages with timeout=0 (non-blocking)
                method_frame, properties, body = self.channel.basic_get(
                    queue=self.response_queue,
                    auto_ack=True
                )
                
                if method_frame:
                    # Message received
                    try:
                        message = json.loads(body.decode())
                        self.message_received.emit(message)
                        self.logger.debug("Message received and processed")
                    except Exception as e:
                        self.logger.error(f"Error processing message: {e}")
                
                # Process connection events
                self.connection.process_data_events()
                
            except Exception as e:
                self.logger.error(f"Error processing RabbitMQ events: {e}")
                self.is_connected = False
                self.connection_status_changed.emit(False)