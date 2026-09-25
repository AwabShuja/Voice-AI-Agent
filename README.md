# Voice AI Patient Registration

A synthetic patient registration assessment built with FastAPI, SQLite, Vapi, and
Google Gemini. A caller supplies demographics, corrects mistakes, hears the complete readback,
and explicitly confirms before the application creates a patient record.

**Use fictional patient information only.** Automated testing is the sole bonus
feature; the application does not include a patient dashboard or returning-caller matching.

## Delivery status

| Item | Current value |
| --- | --- |
| Local API | `http://127.0.0.1:8000` after starting the application |
| API documentation | `https://impermissible-brittney-supercerebral.ngrok-free.dev/docs` |
| Live phone number | `+1 (302) 754-2013` |
| Public API base URL | `https://impermissible-brittney-supercerebral.ngrok-free.dev` |
| Private repository URL | `https://github.com/AwabShuja/Voice-AI-Agent` (reviewer invitation required) |
| Live phone acceptance | **Not yet verified** |

The implementation includes the application, migration, automated tests, assistant
configuration generator, provider checks, Docker configuration, and Azure runbook.
Complete the remaining live-call and persistence checks in
[the acceptance record](docs/ACCEPTANCE.md) before submission.

## Local setup (Windows PowerShell)

Install Python 3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/).
From this repository's root:

```powershell
uv sync --locked
python scripts/init_local.py
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Open `/docs`. Select **Authorize**, then enter the `API_KEY` value from your local
`.env` for the patient API. Do not put `Bearer` in front of this key. The separate
Vapi bearer credential is only for webhook requests.

From another terminal, verify the running API without creating any records:

```powershell
uv run python -m scripts.check_api
```

The initialization script creates random, distinct API and webhook secrets and never
overwrites an existing `.env`. Neither Gemini nor Vapi credentials are needed to run
the REST API or automated tests. The local SQLite file is `data/patients.db`.

On Linux/macOS the same `uv` commands work. Python 3.13 is required. To run with
Docker Desktop after starting its Linux container engine:

```powershell
python scripts/init_local.py
docker compose up --build -d api
docker compose logs -f api
```

The container runs migrations before Uvicorn starts. On Linux, create the host
`data` directory with ownership `10001:10001` first; see the Azure runbook.

## Connect the voice assistant

For a field-by-field account setup walkthrough, use the
[credentials and ngrok guide](docs/SETUP_CREDENTIALS.md).

1. Sign into Vapi, Google AI Studio, and ngrok. Verify your **actual remaining credits** and
   the intended review window. Leave Vapi auto-reload off; no scripts here purchase
   credits, change subscriptions, or buy paid phone numbers.
2. Put `VAPI_API_KEY`, `GEMINI_API_KEY`, `NGROK_AUTHTOKEN`, and `NGROK_DOMAIN` in `.env`.
   `NGROK_DOMAIN` is the assigned hostname without `https://` or a path.
3. In Vapi **Integrations**, connect your Google Gemini API key. The selected model is
   `gemini-3.5-flash`, served by Google. The backend does not proxy LLM inference.
   Deepgram recognition and speech use Vapi's integration and available credits.
4. In Vapi's **Server Configuration** integration, create a bearer credential using
   the local `VAPI_WEBHOOK_SECRET`, with the `Authorization` header and bearer prefix
   enabled. Put the resulting credential ID into `VAPI_CREDENTIAL_ID`.
5. With the local API running, open another terminal and run:

   ```powershell
   uv run python -m scripts.start_tunnel
   ```

6. Set `PUBLIC_BASE_URL=https://YOUR_ASSIGNED_NGROK_DOMAIN` in `.env`. Check
   `PUBLIC_BASE_URL/health`. Browser visitors may need to dismiss ngrok's free-tier
   interstitial; ordinary server-to-server webhook traffic does not use that page.
   You can verify it with `uv run python -m scripts.check_api --base-url https://YOUR_ASSIGNED_NGROK_DOMAIN`.
7. Check API access and generate the assistant configuration:

   ```powershell
   uv run python -m scripts.preflight --online
   uv run python -m scripts.configure_vapi
   ```

8. Review `.local/vapi-assistant.json`, then configure the assistant and request a
   free Vapi U.S. number:

   ```powershell
   uv run python -m scripts.configure_vapi --apply
   ```

The script records successful resource IDs in `.local/vapi-resources.json` and reuses
them on subsequent runs. You can provide existing IDs in `.env` instead. Back up
these IDs privately. If a network timeout occurs after creating a resource, inspect
the Vapi dashboard and set its ID before retrying. Do not automatically create more
resources to resolve ambiguous timeouts. If a free number is unavailable, document
the exact attempt and provider response in the acceptance record.

Use Vapi's browser **Talk to Assistant** to check the prompt and tools. Then make a
real inbound call to the provisioned number. Browser testing alone does not satisfy
the assignment. Verify U.S. number reachability from the reviewer's calling service.
The configured limit is 15 minutes per call; available credits still govern usage.

Official integration references: [Google Gemini](https://docs.vapi.ai/providers/model/gemini),
[Deepgram STT](https://docs.vapi.ai/providers/transcriber/deepgram),
[Deepgram TTS](https://docs.vapi.ai/providers/voice/deepgram),
[webhook authentication](https://docs.vapi.ai/server-url/server-authentication),
[free numbers](https://docs.vapi.ai/free-telephony),
[billing](https://docs.vapi.ai/billing/manage-billing-and-credits).

## Architecture and project structure

```text
Phone -> Vapi (Deepgram STT -> Gemini -> Deepgram TTS)
                  |
                  | authenticated synchronous tool calls
                  v
             FastAPI webhook -----> Registration service
                                           |
Reviewer -> FastAPI patient routes ------> Patient service -> SQLAlchemy -> SQLite
```

```text
app/
  api/          HTTP routes, webhook adapter, provider response format
  core/         Environment settings, authentication, errors, JSON logging
  db/           SQLite engine and session lifecycle
  models/       Database entities and UTC timestamp handling
  schemas/      Pydantic demographics and response types
  services/     Patient CRUD and registration business rules
  voice/        Call drafts, tool schemas, assistant config, annotated prompt
migrations/     Alembic schema history
tests/          API, voice integration, provider mocks, real process restart test
scripts/        Environment initialization, preflight, provisioning, tunnel, backup
deploy/         Container startup and Azure deployment runbook
docs/           Manual acceptance and delivery record
```

FastAPI provides validation and interactive API documentation. SQLAlchemy keeps
database operations explicit, and Alembic provides repeatable schema initialization
without destructive startup behavior. SQLite suits this single-instance assessment;
its file must remain on durable storage. Vapi manages streaming audio and interruptions
while Gemini generates conversational responses and tool calls. Using a managed voice
pipeline keeps the custom code focused on registration behavior.

The annotated [system prompt](app/voice/prompt.md) is included with the code. The
assistant configuration and tool schemas are generated from the same Python schemas
used by the server, avoiding a separately maintained set of demographic tool fields.

## Registration and confirmation behavior

`update_registration` records supplied fields and reports missing/invalid values.
An invalid correction removes the old field from the draft so it cannot silently be
saved. Once required fields and the optional offer are complete, `prepare_registration`
returns every supplied value, a full readback, and an opaque confirmation token.

The assistant reads all details and waits for explicit consent. Any correction
invalidates the token. `save_registration` accepts only that prepared version and
`caller_confirmed: true`. Patient creation and the per-call receipt are committed in
one transaction. Repeating a successful save with the same call and token returns
the original patient, including after a process restart. New independent calls may
create additional records; returning-patient recognition is outside the chosen scope.

The token checks enforce snapshot consistency, but the LLM's confirmation assertion
is not independent proof that audio played completely or that a human consented.
The prompt explicitly separates readback and the following user turn; live testing
must verify actual speech, interruptions, and consent handling.

Unfinished drafts expire after 30 minutes, disappear on process restart, and are
discarded on hangup or start-over. They are never automatically converted into
patients. A disconnect during a confirmed commit may leave a saved patient; consult
the API/logged patient ID. End-of-call reports never create records.

## Data validation

| Fields | Rules |
| --- | --- |
| First/last names | 1–50 characters; Unicode letters, hyphens, apostrophes; at least one letter |
| Birth date | Real date, no future dates, exact `MM/DD/YYYY`; no assumed age cutoff |
| Sex | `Male`, `Female`, `Other`, `Decline to Answer` |
| Patient/emergency phones | Normalize punctuation and optional leading `1`; validate U.S. numbering metadata and store ten digits |
| Email | Valid email syntax; optional |
| Address line 1 | Required, nonblank, maximum 200 characters |
| Address line 2 | Optional, maximum 200 characters |
| City | 1–100 characters |
| State | Two-letter abbreviation; 50 states plus DC; normalized uppercase |
| ZIP | Five digits or `12345-6789`; preserve leading zeros |
| Insurance provider | Optional, maximum 100 characters |
| Insurance member ID | Optional, 1–100 ASCII alphanumeric characters |
| Preferred language | Optional, maximum 100 characters, defaults to English when omitted |
| Emergency contact name | Optional, maximum 100 characters; spaces allowed |

Optional fields accept `null` to clear them; supplied empty strings are invalid.
Required fields cannot be null. Unknown input fields and attempts to supply generated
IDs/timestamps are rejected. Phone validation checks numbering rules, not ownership
or whether a line is active. Email validation does not send verification messages.
Addresses and ZIP/state combinations are not checked against a postal database.

## REST API

Send `X-API-Key` on all patient endpoints. The public `/health`, `/docs`, and
`/openapi.json` endpoints contain no patient records or credentials.

| Method | Endpoint | Successful response |
| --- | --- | --- |
| GET | `/patients` | `200`, active patients as an array |
| GET | `/patients/{patient_id}` | `200`, one active patient |
| POST | `/patients` | `201`, created patient including UUID and UTC timestamps |
| PUT | `/patients/{patient_id}` | `200`, updated patient; omitted fields preserved |
| DELETE | `/patients/{patient_id}` | `200`, ID and soft-deletion timestamp |

List filters are `last_name` (case-insensitive exact match), `date_of_birth`
(`MM/DD/YYYY`), and `phone_number` (normalized). Multiple filters combine with AND.
All matches are returned, newest first. No matches returns an empty array.
Deleted patients are excluded from list/get and return `404` for further updates or
deletes. They remain in SQLite. Partial updates preserve `created_at` and advance
`updated_at`; deletion advances `updated_at` too.

Success: `{"data": ..., "error": null}`.
Failure: `{"data": null, "error": {"code": "...", "message": "...", "details": ...}}`.
Errors use `400` for malformed JSON/empty updates, `401` for bad credentials, `404`
for missing/deleted records, `422` for validation, and `500` for unexpected failures.
Health can return `503` if the database is unavailable. Internal exception details
and database parameters are never returned to callers.

Example fictional patient (also usable in Swagger):

```json
{
  "first_name": "Jane",
  "last_name": "O'Neil",
  "date_of_birth": "02/29/2000",
  "sex": "Female",
  "phone_number": "2025550143",
  "address_line_1": "123 Example Street",
  "city": "Boston",
  "state": "MA",
  "zip_code": "02108"
}
```

On Linux/macOS, with your key set privately as `PATIENT_API_KEY`:

```bash
curl -H "X-API-Key: $PATIENT_API_KEY" \
  'http://127.0.0.1:8000/patients?last_name=O%27Neil&date_of_birth=02%2F29%2F2000'
```

PowerShell equivalent, using a key already held in `$env:PATIENT_API_KEY`:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/patients' `
  -Headers @{ 'X-API-Key' = $env:PATIENT_API_KEY }
```

`POST /vapi/webhook` is a separate provider interface protected by a bearer secret.
It accepts synchronous `tool-calls`, validates arguments, and returns HTTP `200`
with string `result`/`error` entries correlated to each `toolCallId`. This provider
envelope intentionally differs from the public patient API envelope. Authentication
and malformed webhook-envelope failures still use normal HTTP error statuses.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `API_KEY` | Required patient API secret, minimum 32 characters |
| `VAPI_WEBHOOK_SECRET` | Required, distinct webhook bearer secret, minimum 32 characters |
| `DATABASE_URL` | File-backed SQLite URL; local default `sqlite:///./data/patients.db` |
| `LOG_LEVEL` | Application log level; default INFO |
| `DRAFT_TTL_SECONDS` | Draft inactivity expiry; default 1800 |
| `MAX_DRAFTS` | Maximum simultaneous drafts; default 1000 |
| `VAPI_API_KEY` | Private Vapi key used by setup scripts |
| `GEMINI_API_KEY` | Google AI Studio key used by online preflight; also configure it privately in Vapi Integrations |
| `GEMINI_MODEL` | Default `gemini-3.5-flash`; may be changed to another Google model supported by Vapi |
| `VAPI_CREDENTIAL_ID` | Vapi bearer credential referencing the webhook secret |
| `VAPI_ASSISTANT_ID` | Optional existing assistant ID for repeatable configuration |
| `VAPI_PHONE_NUMBER_ID` | Optional existing number ID to attach |
| `VAPI_AREA_CODE` | Desired free U.S. area code; default 202, subject to inventory |
| `PUBLIC_BASE_URL` | Reachable HTTPS origin used for Vapi webhooks |
| `NGROK_AUTHTOKEN` | ngrok authentication; never included in generated assistant JSON |
| `NGROK_DOMAIN` | Account's assigned ngrok hostname, without scheme/path |

Docker passes only application settings to the API container and the ngrok token to
the tunnel container. Database files, local generated configuration, logs, private
keys, and `.env` are ignored by Git and excluded from the Docker build context.

## Tests and observability

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Tests apply real Alembic migrations to temporary SQLite files. They cover CRUD,
filters, validation, auth, soft deletion, draft corrections, confirmation tokens,
call isolation, concurrency, rollback after a staged insert, and idempotent retries.
A process test starts two separate Uvicorn servers in succession and verifies the
first server's record survives before creating another. Provider provisioning uses
HTTPX mocks, so the test suite consumes no voice credits. GitHub Actions runs these
checks on Python 3.13.

JSON stdout events include `registration_prepared`, `registration_saved`,
`registration_abandoned`, `registration_reset`, and `voice_tool_failed`. The prepared
and saved events include the final synthetic demographic payload as required by the
assessment. Credentials and confirmation tokens are not logged. Keep INFO enabled
during review. Container logs rotate at 10 MB, keeping three files per service.

## Persistence, deployment, and backup

Follow [the Azure for Students deployment runbook](deploy/AZURE.md). The important
invariant is that `data/patients.db` and its SQLite WAL files live on the VM's persistent
Azure managed disk, outside the container layer.
Run one application instance/worker because unfinished drafts are process-local.
The API and ngrok both restart automatically under Compose; the laptop can be off.

Create a consistent local backup using SQLite's online backup API:

```powershell
uv run python -m scripts.backup_db
```

It writes an ignored `.local/backups` file. Do not copy a live SQLite database file
alone while WAL is active. For rollback, stop the API, restore a consistent backup
to a fresh database path, set `DATABASE_URL` to that path, and start the matching
application version. Container deployments use the mounted `/app/data` path.

## Trade-offs, troubleshooting, and next steps

- This is a synthetic assessment application, not a healthcare production deployment.
- Speech quality, interrupted readbacks, and actual consent must be tested on a live
  call. Automated API tests cannot establish these properties.
- SQLite supports this single-instance workload. Multi-instance deployment would
  require shared conversation state and a different database architecture.
- API-key access is intentionally simple. No accounts, roles, or identity verification
  are included. Provide the reviewer key privately.
- No transcript or audio is stored by this application. Audio/packet capture is
  disabled in the assistant config; Vapi may retain its own operational call logs.
- If the app reports an uninitialized database, run `uv run alembic upgrade head`.
- A webhook `401` usually means the Vapi credential does not match the backend secret.
  Recheck the bearer prefix and the credential ID on the assistant and each tool.
- If the agent reports no tool result, check the public HTTPS URL and correlated
  result strings in the Vapi dashboard. Server logs identify failed calls by call ID.
- Free-credit exhaustion or ngrok/Azure limits can interrupt review availability.
  Check balances and expiry beforehand; do not enable paid reloads as a workaround.
- If Docker reports a missing engine on Windows, start Docker Desktop with Linux
  containers, or continue using the native Python instructions.

Remaining delivery work is account setup/verification, real U.S. number provisioning,
Azure deployment and reboot verification, live conversation acceptance, and private
GitHub publication/reviewer access. Record actual outcomes and blockers in
[the acceptance record](docs/ACCEPTANCE.md); replace the pending submission fields above.
