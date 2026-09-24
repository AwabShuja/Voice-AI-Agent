# AWS EC2 deployment runbook

## Account and instance prerequisites

Use the existing account's active credits. In Billing, confirm the remaining balance,
expiry, and coverage for EC2, EBS, and public IPv4 for the entire review window. Keep
Vapi usage within its existing free credits; do not enable automatic top-ups.

Create one instance in `us-east-1` with:

- Ubuntu Server 24.04 LTS, x86_64; `t3.micro` initially.
- An encrypted 16 GiB `gp3` EBS root volume. Retain the volume on termination if
  its records must outlive the instance; retention continues consuming storage.
- One security group permitting SSH (22) from your current IP only. Do not open
  port 8000. ngrok establishes an outbound HTTPS tunnel, so inbound 80/443 are unnecessary.
- An SSH key controlled by you. The application itself needs no AWS access keys.

No AWS resources were created automatically by the repository. Record the instance
ID and selected volume in your private deployment notes.

## Prepare the instance

SSH to the instance. Install Docker Engine and the Compose plugin using
[Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/).
Enable Docker at boot with `sudo systemctl enable --now docker`.

Transfer the repository to `/opt/voice-patient-registration` by cloning the private
repository with a read-only deploy key, or securely copying the source. Exclude your
Windows `.venv`, caches, and local database. Do not put a GitHub token into a clone URL.
Separately transfer the `.env` file using SSH, or create it privately on the server.

```bash
cd /opt/voice-patient-registration
chmod 600 .env
sudo install -d -m 0750 -o 10001 -g 10001 data
sudo docker compose config --quiet
sudo docker compose up --build -d api
curl --fail http://127.0.0.1:8000/health
```

The `data` directory is on the EBS root volume and mounted into the non-root API
container. Do not deploy over that directory or remove it during application updates.
The container always runs `alembic upgrade head`; it never drops/recreates the database.

Set the assigned `NGROK_DOMAIN` and `NGROK_AUTHTOKEN` in the server `.env`, then run:

Stop the laptop's tunnel with Ctrl+C before moving that same domain to EC2.

```bash
sudo docker compose --profile public up -d
sudo docker compose ps
sudo docker compose logs --tail 50 api ngrok
```

Check `https://YOUR_ASSIGNED_NGROK_DOMAIN/health` from another computer. Run the local
Vapi configuration script with this origin and the same webhook secret/credential.
The backend API key should also match the private key provided to the reviewer.

## Verify review readiness

1. Make a real call and create a fictional patient. Keep the returned/logged patient
   UUID and verify it using the authenticated API.
2. Run `sudo docker compose restart api`; query the same UUID again.
3. Reboot the instance, reconnect, and verify both containers are running.
4. Query the same UUID through the public HTTPS API after reboot.
5. Make a second real call and verify both records are available.
6. Record the phone number, public API origin, repository URL, review window, and
   results in the README and acceptance record. Share the API key privately.

For updates, create a database backup first, then deploy the new source and run
`sudo docker compose --profile public up --build -d`. The bind-mounted database
survives container replacement. Schedule updates outside active calls because drafts
are process-local.

## Backups and monitoring

Create a consistent database backup inside the mounted volume:

```bash
sudo docker compose exec api python -m scripts.backup_db \
  --destination /app/data/patients-backup-before-update.db
```

Choose a new filename each time; existing backups are never overwritten. Transfer
the backup privately off the instance if protection against losing EBS is needed.
Retain only the backups you need within the credit allowance.

Check `/health`, `docker compose ps`, and the `registration_saved`/`voice_tool_failed`
events during the review window. Docker logs rotate automatically. Check AWS credit
and Vapi balances before each live session. An EBS-backed file protects against
process/container/instance reboots, not deliberate volume deletion.

After the review, stop the application/tunnel if no longer needed. Decide when to
remove AWS resources and retained volumes based on the required record retention;
this runbook does not delete them automatically.
