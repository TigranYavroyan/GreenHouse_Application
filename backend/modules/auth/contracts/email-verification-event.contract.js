import { MESSAGE_EVENTS } from '../../common/messaging/messaging.constants.js';

const EVENT_VERSION = 1;

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

export function buildEmailVerificationEvent({
  messageId,
  correlationId,
  payload,
}) {
  return {
    messageId,
    eventName: MESSAGE_EVENTS.NOTIFICATION_EMAIL_VERIFICATION_REQUESTED,
    eventVersion: EVENT_VERSION,
    occurredAt: new Date().toISOString(),
    correlationId,
    payload,
  };
}

export function validateEmailVerificationEvent(event) {
  if (!event || typeof event !== 'object') {
    return { valid: false, error: 'Event must be an object' };
  }
  if (!isNonEmptyString(event.messageId)) {
    return { valid: false, error: 'messageId is required' };
  }
  if (event.eventName !== MESSAGE_EVENTS.NOTIFICATION_EMAIL_VERIFICATION_REQUESTED) {
    return { valid: false, error: 'eventName is invalid' };
  }
  if (event.eventVersion !== EVENT_VERSION) {
    return { valid: false, error: 'eventVersion is invalid' };
  }
  if (!isNonEmptyString(event.occurredAt)) {
    return { valid: false, error: 'occurredAt is required' };
  }
  if (!isNonEmptyString(event.correlationId)) {
    return { valid: false, error: 'correlationId is required' };
  }
  if (!event.payload || typeof event.payload !== 'object') {
    return { valid: false, error: 'payload is required' };
  }

  const { userId, email, username, verificationToken, verificationUrl } = event.payload;
  if (!isNonEmptyString(userId)) {
    return { valid: false, error: 'payload.userId is required' };
  }
  if (!isNonEmptyString(email)) {
    return { valid: false, error: 'payload.email is required' };
  }
  if (!isNonEmptyString(username)) {
    return { valid: false, error: 'payload.username is required' };
  }
  if (!isNonEmptyString(verificationToken)) {
    return { valid: false, error: 'payload.verificationToken is required' };
  }
  if (!isNonEmptyString(verificationUrl)) {
    return { valid: false, error: 'payload.verificationUrl is required' };
  }

  return { valid: true };
}

