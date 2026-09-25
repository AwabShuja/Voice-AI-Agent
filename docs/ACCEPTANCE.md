# Acceptance and submission record

Requirements source: the take-home assessment brief supplied by CareCloud.
Only synthetic data may be used. Automated tests are the sole selected bonus.

## Automated evidence

Run `uv run pytest -q`, `uv run ruff check .`, and `uv run ruff format --check .`.
The test suite exercises actual migrations, temporary SQLite databases, HTTP
requests, a separate-process restart, and mocked Vapi provisioning. Automated
results do not establish real phone reachability or speech quality.

Latest local verification (2026-09-24):

- The **54-test full-suite baseline passed**, including the separate-process HTTP
  restart test. The Gemini switch adds one provider-preflight test (55 now collect);
  both affected Gemini configuration/preflight tests pass locally.
- Ruff lint and formatting checks passed.
- Alembic reported no pending schema differences.
- Docker Compose configuration validation passed.
- The Docker image built successfully. A separate test container ran migrations,
  created a fictional patient, restarted, and returned the same patient afterward.
  The temporary container was removed after verification; its database was isolated
  from the normal application database.
- Read-only checks against the running native API passed: health, Swagger,
  authenticated patient listing, and rejection of unauthenticated access.
- The local application database is empty; no seed records were inserted.

The installed Starlette version emits one deprecation warning for its HTTPX-based
test client. Tests pass with the locked dependencies; this does not affect runtime
patient API behavior.

| Requirement | Evidence |
| --- | --- |
| Complete demographic model and server validation | `tests/test_patients.py` |
| CRUD, filters, envelopes, HTTP statuses, API key | `tests/test_patients.py` |
| UUID/UTC metadata, partial updates, soft deletion | `tests/test_patients.py` |
| Records survive a real application process restart | `tests/test_process_restart.py` |
| Field errors, corrections, optional defaults, full readback payload | `tests/test_voice.py` |
| Prepare/confirm/save, stale token rejection, start over | `tests/test_voice.py` |
| Dropped call before save, retry safety, transaction rollback | `tests/test_voice.py` |
| Gemini/Deepgram config, credentials, bounded draft state | `tests/test_configuration.py` |
| Idempotent free-number setup with partial failure handling | `tests/test_configuration.py` |

## Manual voice scenarios

Record the date, provider call ID, outcome, and any corrective change for each.

- [ ] Call the actual U.S. number from the reviewer's calling service.
- [ ] Provide required fields out of order; verify the agent retains already supplied fields.
- [ ] Give a three-digit phone, a future/invalid birth date, and an invalid ZIP; verify
      the agent asks about the affected field rather than guessing or restarting.
- [ ] Correct the spelling of the last name and hear the corrected spelling later.
- [ ] Decline optional information; complete registration without being pressured.
- [ ] On another call, supply all optional fields and verify every supplied value is read back.
- [ ] Interrupt the readback and correct a value; verify a complete fresh readback
      and a new explicit confirmation occur before saving.
- [ ] Say "start over"; verify the old draft is not saved or reused.
- [ ] Hang up before confirming; verify no patient was created.
- [ ] Confirm a full readback; hear success only after persistence, then a graceful hangup.
- [ ] Retrieve the record with the reviewer API key.
- [ ] Verify a graceful save-failure/retry response in a controlled test environment.
- [ ] Restart the backend and reboot the Azure VM; retrieve the original UUID afterward.
- [ ] Make another call and verify the first registration remains available.

## Account and live delivery blockers

The application is deployed to an Azure VM through Docker Compose, exposed through an
assigned ngrok HTTPS domain, and connected to a Vapi-managed U.S. number. Remaining
credit, live-call, and full VM-reboot checks must still be recorded by the operator.

Fill in after setup:

| Check | Verified result |
| --- | --- |
| Vapi available free credits; auto-reload off | Pending |
| Gemini model access and integration | API access and Vapi assistant configuration verified |
| ngrok assigned domain and HTTPS reachability | Public health, Swagger, and authenticated API checks passed |
| Azure for Students credit, expiry, B1s quota, and managed disk coverage | Pending |
| Review window | Pending |
| U.S. number inventory and inbound reachability | Number provisioned; real inbound reachability pending |
| Azure VM restart/reboot persistence | Pending |
| Private repository and reviewer invitations | Repository created; reviewer invitation pending |

If number provisioning fails, record the date, requested area code, operation, HTTP
status, provider's non-secret explanation, and attempted resolution here. Do not
label missing credentials as a vendor failure. Provide the native local setup and
browser-test instructions even if the external blocker remains.

## Submission checklist

- [ ] Replace pending phone/API/repository values in README with verified live values.
- [ ] Share the reviewer API key through an agreed private channel.
- [ ] Push to a private GitHub repository and invite the supplied reviewer accounts.
- [ ] Confirm Git excludes `.env`, data files, logs, and private keys.
- [ ] Include setup, architecture, stack rationale, annotated prompt, tests, and limitations.
- [ ] Keep the Azure VM, ngrok, Vapi, and adequate credits available throughout review.

For GitHub publication, after authenticating your own GitHub CLI and reviewing files:

```bash
git add .
git commit -m "Implement voice patient registration assessment"
gh repo create YOUR_REPOSITORY_NAME --private --source=. --remote=origin --push
```

If the destination already exists, add its remote and push the current branch instead
of creating another repository. Grant reviewer access from the repository's settings.
Do not commit testing credentials or actual database records.
