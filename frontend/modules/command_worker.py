import pika
import json
import uuid
import logging
import time
import os
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class CommandWorker(QObject):
    response_received = pyqtSignal(dict)
    connection_status = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # Use environment variables with Docker fallbacks
        self.host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        self.port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.username = os.getenv('RABBITMQ_USER', 'guest')
        self.password = os.getenv('RABBITMQ_PASS', 'guest')
        
        self.connection = None
        self.channel = None
        self.consuming = False
        self.logger = logging.getLogger('CommandWorker')
        self.pending_commands = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.consumer_tag = None
        
        # Use QTimer for periodic checks instead of threads
        self.consumer_timer = QTimer()
        self.consumer_timer.timeout.connect(self._check_for_messages)
        self.consumer_timer.setInterval(100)  # Check every 100ms
        
        self.logger.info(f"Initializing CommandWorker for RabbitMQ at {self.host}:{self.port}")
        
    def setup_rabbitmq(self):
        try:
            # Clean up existing connection
            self.disconnect()
            
            self.logger.info(f"Creating new RabbitMQ connection to {self.host}:{self.port}...")
            
            # Create connection with environment variables
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare queues (let server handle arguments)
            self.channel.queue_declare(queue='greenhouse_commands', durable=True)
            self.channel.queue_declare(queue='command_responses', durable=True)
            
            # Set QoS
            self.channel.basic_qos(prefetch_count=10)
            
            self.connection_status.emit(True)
            self.logger.info("Successfully connected to RabbitMQ")
            
            # Start the message checker
            self.consumer_timer.start()
            self.consuming = True
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to RabbitMQ at {self.host}:{self.port}: {str(e)}")
            self.connection_status.emit(False)
            return False
    
    def _check_for_messages(self):
        """Check for incoming messages (non-blocking)"""
        if not self.connection or not self.channel:
            return
            
        try:
            # Non-blocking check for messages
            method_frame, header_frame, body = self.channel.basic_get(
                queue='command_responses', 
                auto_ack=False
            )
            
            if method_frame:
                # We got a message!
                try:
                    response = json.loads(body.decode())
                    command_id = response.get('commandId', 'unknown')
                    self.logger.info(f"Received response for command: {command_id}")
                    
                    # Acknowledge the message
                    self.channel.basic_ack(method_frame.delivery_tag)
                    
                    # Emit the response
                    self.response_received.emit(response)
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON response: {str(e)}")
                    self.channel.basic_nack(method_frame.delivery_tag, requeue=False)
                except Exception as e:
                    self.logger.error(f"Error processing response: {str(e)}")
                    self.channel.basic_nack(method_frame.delivery_tag, requeue=False)
                    
        except Exception as e:
            self.logger.error(f"Error checking for messages: {str(e)}")
            # If we get an error, try to reconnect
            self.connection_status.emit(False)
            self.consuming = False
            self.consumer_timer.stop()
    
    def send_command(self, command_data):
        try:
            # Check if we need to reconnect
            if not self.connection or self.connection.is_closed:
                self.logger.warning("Connection closed, attempting reconnect...")
                if not self.setup_rabbitmq():
                    return False
            
            # Send the command
            self.channel.basic_publish(
                exchange='',
                routing_key='greenhouse_commands',
                body=json.dumps(command_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # persistent
                    content_type='application/json'
                )
            )
            
            command_id = command_data.get('commandId', 'unknown')
            self.pending_commands[command_id] = command_data
            self.logger.info(f"Command {command_id} sent successfully: {command_data.get('command', 'unknown')}")
            return True
            
        except pika.exceptions.ConnectionClosed:
            self.logger.error("Connection closed while sending command")
            self.connection_status.emit(False)
            return False
        except Exception as e:
            self.logger.error(f"Error sending command: {str(e)}")
            self.connection_status.emit(False)
            return False
    
    def attempt_reconnect(self):
        """Attempt to reconnect"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached")
            return False
            
        delay = 2  # Short delay for quick retry
        self.logger.info(f"Attempting reconnect in {delay} seconds (attempt {self.reconnect_attempts + 1})")
        time.sleep(delay)
        
        self.reconnect_attempts += 1
        success = self.setup_rabbitmq()
        if success:
            self.reconnect_attempts = 0
        return success
    
    def disconnect(self):
        self.logger.info("Disconnecting from RabbitMQ...")
        self.consuming = False
        self.consumer_timer.stop()
        
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
        except Exception as e:
            self.logger.error(f"Error closing channel: {str(e)}")
        
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
        except Exception as e:
            self.logger.error(f"Error closing connection: {str(e)}")
        
        self.logger.info("Disconnected from RabbitMQ")