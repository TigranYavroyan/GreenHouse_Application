// clients/rabbitmqClient.js
import amqp from 'amqplib';
import SystemLogger from '../logger/systemLogger.js';
import config from '../config/index.js';

class RabbitMQClient {
  constructor() {
    this.connection = null;
    this.channel = null;
    const { host, port } = config.rabbitmq;
    this.url = `amqp://${host}:${port}`;
  }

  async connect() {
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
        setTimeout(() => this.connect().catch(() => {}), 5000);
      });
      return this.channel;
    } catch (err) {
      SystemLogger.error(`RabbitMQ connect failed: ${err.message}`);
      setTimeout(() => this.connect().catch(() => {}), 5000);
      throw err;
    }
  }

  async assertQueue(name, opts = { durable: true }) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.assertQueue(name, opts);
  }

  async prefetch(count) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.prefetch(count);
  }

  sendToQueue(queue, buffer, opts) {
    if (!this.channel) throw new Error('RabbitMQ channel not available');
    return this.channel.sendToQueue(queue, buffer, opts);
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
}

export default RabbitMQClient;
