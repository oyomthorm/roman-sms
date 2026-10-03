# Pahappa Comms API notes

The API is documented at
`https://pahappa.com/docs/comms` (or the URL provided with your
credentials). This file records the parts that matter for Roman SMS
and the constraints we discovered the hard way.

## Endpoints

| Purpose | URL | Method |
|---|---|---|
| Send SMS | `https://comms.egosms.co/api/v1/json/` | POST |
| Balance | `https://comms.egosms.co/api/v1/json/` | POST |
| Sandbox | `https://comms-test.pahappa.net/api/v1/json/` | POST |
| Delivery webhook | Your URL, registered in the portal | POST (they call us) |

## Credentials

- **Live credentials** are issued by Pahappa support. There is no
  self-service signup for the API.
- **Sandbox credentials** are separate. Register on the sandbox domain
  separately. Sandbox credentials do not work on live; live credentials
  do not work on sandbox.
- Store both in `.env`. Toggle with `EGOSMS_SANDBOX=1` for sandbox.
  **The comparison is `== '1'` — any other value (including `true`)
  evaluates to False.** Use `0` for live.
- Rotate the password immediately if it ever appears in a log file or
  a chat message.

## Request shape — SendSms

```json
{
  "method": "SendSms",
  "userdata": {"username": "...", "password": "..."},
  "msgdata": [
    {"number": "256700123456",
     "message": "...",
     "senderid": "ROMANSMS",
     "priority": 1}
  ]
}