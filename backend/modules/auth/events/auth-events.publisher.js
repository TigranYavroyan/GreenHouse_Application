import { randomUUID } from 'crypto';
import {
  MESSAGE_EXCHANGES,
  MESSAGE_ROUTING_KEYS,
} from '../../common/messaging/messaging.constants.js';
import {
  buildEmailVerificationEvent,
  validateEmailVerificationEvent,
} from '../contracts/email-verification-event.contract.js';

class AuthEventsPublisher {
  constructor({ rabbitClient }) {
    this.rabbitClient = rabbitClient;
  }

  publishVerificationEmailRequested(payload) {
    const event = buildEmailVerificationEvent({
      messageId: randomUUID(),
      correlationId: payload.userId,
      payload,
    });

    const validation = validateEmailVerificationEvent(event);
    if (!validation.valid) {
      throw new Error(`Invalid verification event payload: ${validation.error}`);
    }

    const published = this.rabbitClient.publish(
      MESSAGE_EXCHANGES.EVENTS_V1,
      MESSAGE_ROUTING_KEYS.NOTIFICATION_EMAIL_VERIFICATION_REQUESTED_V1,
      Buffer.from(JSON.stringify(event)),
      {
        contentType: 'application/json',
        contentEncoding: 'utf-8',
        persistent: true,
        messageId: event.messageId,
        timestamp: Date.now(),
        correlationId: event.correlationId,
      }
    );

    if (!published) {
      throw new Error('Failed to publish email verification event');
    }

    return event;
  }
}

export default AuthEventsPublisher;

