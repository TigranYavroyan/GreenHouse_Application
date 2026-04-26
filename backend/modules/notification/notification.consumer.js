import {
  MESSAGE_QUEUES,
} from '../common/messaging/messaging.constants.js';
import { validateEmailVerificationEvent } from '../auth/contracts/email-verification-event.contract.js';

function readRetryCount(msg) {
  const value = msg?.properties?.headers?.['x-retry-count'];
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function isTransientEmailError(error) {
  if (!error) return false;
  const code = String(error.code || '').toUpperCase();
  if (['ECONNECTION', 'ETIMEDOUT', 'ESOCKET', 'ECONNRESET'].includes(code)) {
    return true;
  }
  if (Number.isFinite(error.responseCode)) {
    return error.responseCode >= 500;
  }
  return false;
}

class NotificationConsumer {
  constructor({ rabbitClient, logger, notificationMailer, maxRetries = 5 }) {
    this.rabbitClient = rabbitClient;
    this.logger = logger;
    this.notificationMailer = notificationMailer;
    this.maxRetries = maxRetries;
  }

  async start() {
    await this.rabbitClient.consume(
      MESSAGE_QUEUES.NOTIFICATION_EMAIL_VERIFICATION_V1,
      async (msg) => {
        if (!msg) return;
        await this.handleMessage(msg);
      },
      { noAck: false }
    );
    this.logger.info('Notification email verification consumer configured');
  }

  async handleMessage(msg) {
    let parsedEvent = null;

    try {
      parsedEvent = JSON.parse(msg.content.toString());
    } catch (parseError) {
      await this.sendToDlq(msg, null, `Invalid JSON payload: ${parseError.message}`);
      this.rabbitClient.ack(msg);
      return;
    }

    const validation = validateEmailVerificationEvent(parsedEvent);
    if (!validation.valid) {
      await this.sendToDlq(msg, parsedEvent, `Invalid event schema: ${validation.error}`);
      this.rabbitClient.ack(msg);
      return;
    }

    try {
      await this.notificationMailer.sendVerificationEmail({
        to: parsedEvent.payload.email,
        username: parsedEvent.payload.username,
        verificationUrl: parsedEvent.payload.verificationUrl,
      });
      this.rabbitClient.ack(msg);
    } catch (emailError) {
      const retryCount = readRetryCount(msg);
      const nextRetry = retryCount + 1;
      const canRetry = nextRetry <= this.maxRetries;
      const transientError = isTransientEmailError(emailError);

      if (transientError && canRetry) {
        const published = this.rabbitClient.sendToQueue(
          MESSAGE_QUEUES.NOTIFICATION_EMAIL_VERIFICATION_RETRY_V1,
          msg.content,
          {
            contentType: 'application/json',
            contentEncoding: 'utf-8',
            persistent: true,
            headers: {
              ...(msg.properties?.headers || {}),
              'x-retry-count': nextRetry,
              'x-last-error': String(emailError.message || 'unknown error'),
            },
            messageId: msg.properties?.messageId,
            timestamp: Date.now(),
            correlationId: msg.properties?.correlationId,
          }
        );

        if (!published) {
          await this.rabbitClient.waitForDrain();
        }

        this.logger.warn(
          `Verification email send failed; queued retry ${nextRetry}/${this.maxRetries} for userId=${parsedEvent.payload.userId}`
        );
        this.rabbitClient.ack(msg);
        return;
      }

      await this.sendToDlq(msg, parsedEvent, `Email send failure: ${emailError.message}`);
      this.rabbitClient.ack(msg);
    }
  }

  async sendToDlq(msg, eventPayload, reason) {
    const dlqPayload = {
      reason,
      failedAt: new Date().toISOString(),
      retryCount: readRetryCount(msg),
      event: eventPayload,
    };

    const published = this.rabbitClient.sendToQueue(
      MESSAGE_QUEUES.NOTIFICATION_EMAIL_VERIFICATION_DLQ_V1,
      Buffer.from(JSON.stringify(dlqPayload)),
      {
        contentType: 'application/json',
        contentEncoding: 'utf-8',
        persistent: true,
        headers: {
          ...(msg.properties?.headers || {}),
          'x-dlq-reason': reason,
        },
        messageId: msg.properties?.messageId,
        timestamp: Date.now(),
        correlationId: msg.properties?.correlationId,
      }
    );

    if (!published) {
      await this.rabbitClient.waitForDrain();
    }

    this.logger.error(`Verification email moved to DLQ: ${reason}`);
  }
}

export default NotificationConsumer;

