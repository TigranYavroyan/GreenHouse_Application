import json
import logging
import queue
import threading
import time
import uuid

import pika
from PyQt5.QtCore import QObject, pyqtSignal

from modules.config import config

class CommandWorker(QObject):
    response_received = pyqtSignal(dict)
    connection_status = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()

        self.host = config.RABBITMQ_HOST
        self.port = config.RABBITMQ_PORT
        self.username = config.RABBITMQ_USER
        self.password = config.RABBITMQ_PASS
        self.session_id = None
        self.response_queue_name = None

        self.logger = logging.getLogger('CommandWorker')
        self.pending_commands = {}
        self.max_reconnect_attempts = 3
        self._reconnect_attempts = 0
        self._running = False
        self._worker_thread = None
        self._stop_event = threading.Event()
        self._outbound = queue.Queue()

        self.logger.info(f"Initializing CommandWorker for RabbitMQ at {self.host}:{self.port}")

    def set_session_id(self, session_id):
        self.session_id = str(session_id or "").strip() or None
        if not self.response_queue_name:
            suffix = self.session_id or uuid.uuid4().hex
            self.response_queue_name = f"command_responses.{suffix}"

    def setup_rabbitmq(self):
        if self._running and self._worker_thread and self._worker_thread.is_alive():
            return True

        self._stop_event.clear()
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, name="rabbit-command-worker", daemon=True)
        self._worker_thread.start()
        return True

    def _create_connection(self):
        credentials = pika.PlainCredentials(self.username, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            heartbeat=120,
            blocked_connection_timeout=30,
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue='greenhouse_commands', durable=True)

        if not self.response_queue_name:
            self.response_queue_name = f"command_responses.{uuid.uuid4().hex}"
        channel.queue_declare(queue=self.response_queue_name, durable=False, auto_delete=True)
        channel.basic_qos(prefetch_count=20)
        return connection, channel

    def _publish_outbound(self, channel):
        while True:
            try:
                command_data = self._outbound.get_nowait()
            except queue.Empty:
                return

            command_id = command_data.get('commandId', 'unknown')
            properties = pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json',
                reply_to=self.response_queue_name,
                correlation_id=command_id,
            )
            channel.basic_publish(
                exchange='',
                routing_key='greenhouse_commands',
                body=json.dumps(command_data),
                properties=properties,
                mandatory=False,
            )
            self.pending_commands[command_id] = command_data
            self.logger.info(f"Command {command_id} sent successfully: {command_data.get('command', 'unknown')}")

    def _on_response(self, channel, method_frame, _header_frame, body):
        try:
            response = json.loads(body.decode())
            command_id = response.get('commandId', 'unknown')
            self.logger.info(f"Received response for command: {command_id}")
            channel.basic_ack(method_frame.delivery_tag)
            self.response_received.emit(response)
        except json.JSONDecodeError as error:
            self.logger.error(f"Failed to parse JSON response: {error}")
            channel.basic_nack(method_frame.delivery_tag, requeue=False)
        except Exception as error:
            self.logger.error(f"Error processing response: {error}")
            channel.basic_nack(method_frame.delivery_tag, requeue=False)

    def _worker_loop(self):
        while not self._stop_event.is_set():
            connection = None
            channel = None
            try:
                self.logger.info(f"Creating RabbitMQ connection to {self.host}:{self.port}...")
                connection, channel = self._create_connection()
                channel.basic_consume(
                    queue=self.response_queue_name,
                    on_message_callback=self._on_response,
                    auto_ack=False,
                )
                self._reconnect_attempts = 0
                self.connection_status.emit(True)
                self.logger.info("Successfully connected to RabbitMQ")

                while not self._stop_event.is_set():
                    self._publish_outbound(channel)
                    connection.process_data_events(time_limit=0.2)
            except Exception as error:
                self.connection_status.emit(False)
                if self._stop_event.is_set():
                    break
                self._reconnect_attempts += 1
                self.logger.error(f"RabbitMQ worker connection error: {error}")
                if self._reconnect_attempts > self.max_reconnect_attempts:
                    self.error_occurred.emit("Max reconnection attempts reached")
                    self._reconnect_attempts = 0
                    time.sleep(2)
                else:
                    backoff_seconds = min(2 ** self._reconnect_attempts, 8)
                    time.sleep(backoff_seconds)
            finally:
                try:
                    if channel and channel.is_open:
                        channel.close()
                except Exception:
                    pass
                try:
                    if connection and connection.is_open:
                        connection.close()
                except Exception:
                    pass

        self.connection_status.emit(False)

    def send_command(self, command_data):
        try:
            if not self._running:
                self.setup_rabbitmq()
            self._outbound.put_nowait(command_data)
            return True
        except Exception as error:
            self.logger.error(f"Error sending command: {error}")
            self.connection_status.emit(False)
            return False

    def attempt_reconnect(self, callback=None):
        success = self.setup_rabbitmq()
        if callback:
            callback(success)
        return success

    def disconnect(self):
        self.logger.info("Disconnecting from RabbitMQ...")
        self._running = False
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.5)
        self._worker_thread = None
        self.logger.info("Disconnected from RabbitMQ")