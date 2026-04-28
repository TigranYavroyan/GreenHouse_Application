# Auth Email Verification Protocol (Monolith Internal Events)

This document describes the production email verification flow implemented in the backend monolith.

Last reviewed against backend implementation: 2026-04-28.

## RabbitMQ Topology

- Exchange: `greenhouse.events.v1` (`topic`, durable)
- Routing key: `notification.email.verification.requested.v1`
- Queues:
  - `notification.email.verification.v1` (primary, durable)
  - `notification.email.verification.retry.v1` (retry, durable, TTL + DL routing)
  - `notification.email.verification.dlq.v1` (dead-letter, durable)

## Event Envelope Schema

```json
{
  "messageId": "uuid",
  "eventName": "notification.email.verification.requested",
  "eventVersion": 1,
  "occurredAt": "2026-03-18T10:00:00.000Z",
  "correlationId": "user-uuid",
  "payload": {
    "userId": "user-uuid",
    "email": "user@example.com",
    "username": "alice",
    "verificationToken": "jwt-token",
    "verificationUrl": "http://localhost:3000/auth/verify-email?token=..."
  }
}
```

Required fields:
- Envelope: `messageId`, `eventName`, `eventVersion`, `occurredAt`, `correlationId`, `payload`
- Payload: `userId`, `email`, `username`, `verificationToken`, `verificationUrl`

## Retry and DLQ Rules

- Consumer validates JSON and schema before processing.
- Invalid JSON/schema is sent directly to `notification.email.verification.dlq.v1`.
- SMTP transient failures are republished to `notification.email.verification.retry.v1` with header:
  - `x-retry-count: <n>`
- Retry queue delays message by `NOTIFICATION_RETRY_DELAY_MS`, then dead-letters it back to primary queue.
- If retry count exceeds `NOTIFICATION_MAX_RETRIES` or error is non-transient, message is moved to DLQ.

## HTTP Auth Contract Changes

- `POST /auth/register`
  - Required body: `username`, `password`, `email`
  - Behavior: create user with `verified=false`, emit verification email event
- `GET /auth/verify-email?token=<jwt>`
  - Behavior: verify JWT (`type=email_verification`), set user `verified=true`
- `POST /auth/login`
  - Behavior: returns `403` when user exists but email is not verified

## Token Rules

- Verification token is JWT with:
  - `sub`: user id
  - `email`: user email
  - `type`: `email_verification`
  - `jti`: unique token id
  - `exp`: default 1 hour (`EMAIL_VERIFICATION_EXPIRES_IN`)
- Verification URL is generated with `PUBLIC_BACKEND_URL`.

