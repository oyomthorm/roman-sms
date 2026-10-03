# Delivery status webhook

Pahappa posts delivery reports to us. This is how `MessageLog.status`
moves from `sent` to `delivered` or `delivery_failed`.

## Endpoint
POST /api/webhooks/transaction-status/<WEBHOOK_TOKEN>
Content-Type: application/json


The token in the URL is compared to `WEBHOOK_TOKEN` in config. A
mismatch returns `404 {"ok": false}` so we do not reveal the endpoint
exists.

This route is CSRF-exempt (`@csrf.exempt`) — Pahappa does not send
our CSRF token.

## Payload

```json
{
  "MsgFollowUpUniqueCode": "08ccf8a77294c34e0b28ad284b39435945",
  "number": "256759001234",
  "Status": "Success",
  "deliveryDate": "2026-08-05T08:58:23.679Z"
}