class MetadataService {
  constructor({ sessionManager, redisClient, rabbitClient, commandStats }) {
    this.sessionManager = sessionManager;
    this.redisClient = redisClient;
    this.rabbitClient = rabbitClient;
    this.commandStats = commandStats;
  }

  getHealth() {
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
      redis: this.redisClient?.isOpen ? 'connected' : 'disconnected',
      rabbitmq: this.rabbitClient?.channel ? 'connected' : 'disconnected',
      sessions: this.sessionManager.listSessions(),
      platform: process.platform,
      totalSessions: this.sessionManager.counter
        ? this.sessionManager.counter - 1
        : 0,
      stats: this.commandStats,
    };
  }

  getStats() {
    return this.commandStats;
  }

  async getQueues() {
    if (!this.rabbitClient?.channel) {
      throw new Error('RabbitMQ channel not available');
    }

    const commandQueue = await this.rabbitClient.checkQueue('greenhouse_commands');
    const responseQueue = await this.rabbitClient.checkQueue('command_responses');

    return {
      commandQueue: {
        messageCount: commandQueue.messageCount,
        consumerCount: commandQueue.consumerCount,
      },
      responseQueue: {
        messageCount: responseQueue.messageCount,
        consumerCount: responseQueue.consumerCount,
      },
    };
  }

  getRootInfo() {
    return {
      message: 'Greenhouse Automation Backend',
      version: '1.0.0',
    };
  }
}

export default MetadataService;