// clients/rabbitmqClient.js
import amqp from 'amqplib';
import SystemLogger from '../logger/systemLogger.js';
import config from '../config/index.js';

class RabbitMQClient {
  constructor() {
    this.connection = null;
    this.channel = null;
    this.isConnecting = false;
    this.connectPromise = null;
    this.reconnectTimer = null;
    this.onConnectHandlers = [];
    const { host, port } = config.rabbitmq;
    this.url = `amqp://${host}:${port}`;
  }

  addOnConnectHandler(handler) {
    if (typeof handler === 'function') {
      this.onConnectHandlers.push(handler);
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer) {
      return;
    }

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect().catch(() => {});
    }, 5000);
  }

  async notifyConnected() {
    for (const handler of this.onConnectHandlers) {
      try {
        await handler(this.channel);
      } catch (err) {
        SystemLogger.error(`RabbitMQ on-connect handler failed: ${err.message}`);
      }
    }
  }

  async connect() {
    if (this.channel) {
      return this.channel;
    }

    if (this.isConnecting) {
      return this.connectPromise;
    }

    this.isConnecting = true;
    this.connectPromise = (async () => {
      try {
        SystemLogger.info(`Connecting to RabbitMQ at: ${this.url}`);
        this.connection = await amqp.connect(this.url);
        this.channel = await this.connection.createChannel();
        this.channel.on('error', (err) => {
          SystemLogger.error(`RabbitMQ channel error: ${err.message}`);
        });
        this.connection.on('error', (err) => {
          SystemLogger.error(`RabbitMQ connection error: ${err.message}`);
        });
        this.connection.on('close', async () => {
          SystemLogger.warn('RabbitMQ connection closed, attempting reconnect in 5s...');
          this.channel = null;
          this.connection = null;
          this.scheduleReconnect();
        });
        await this.notifyConnected();
        return this.channel;
      } catch (err) {
        SystemLogger.error(`RabbitMQ connect failed: ${err.message}`);
        this.scheduleReconnect();
        throw err;
      } finally {
        this.isConnecting = false;
      }
    })();

    return this.connectPromise;
  }

  async assertQueue(name, opts = { durable: true }) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.assertQueue(name, opts);
  }

  async assertExchange(name, type = 'topic', opts = { durable: true }) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.assertExchange(name, type, opts);
  }

  async bindQueue(queue, exchange, routingKey = '') {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.bindQueue(queue, exchange, routingKey);
  }

  async prefetch(count) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.prefetch(count);
  }

  sendToQueue(queue, buffer, opts) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.sendToQueue(queue, buffer, opts);
  }

  publish(exchange, routingKey, buffer, opts) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.publish(exchange, routingKey, buffer, opts);
  }

  consume(queue, onMessage, opts = { noAck: false }) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.consume(queue, onMessage, opts);
  }

  async checkQueue(queue) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.checkQueue(queue);
  }

  ack(msg) {
    if (this.channel && msg) this.channel.ack(msg);
  }

  nack(msg, requeue = true) {
    if (this.channel && msg) this.channel.nack(msg, false, requeue);
  }
}

export default RabbitMQClient;
