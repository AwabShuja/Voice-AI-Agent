# Azure for Students deployment runbook

This guide deploys one FastAPI container and one ngrok container to a single Ubuntu
Azure VM. SQLite remains on a persistent Azure managed OS disk, outside the container
layer, so application, container, and VM restarts preserve patient records. Use only
synthetic patient information.

## Why a virtual machine is the right Azure service

Use a single Azure Linux VM for this assessment:

- Docker Compose can run the API and ngrok exactly as tested locally.
- A managed OS disk provides durable block storage suitable for SQLite and its WAL.
- One VM and one Uvicorn worker preserve the application's in-memory call-draft model.
- The VM can stay reachable throughout the review window.

Azure Container Apps has an attractive free allowance, but its writable container
filesystem is ephemeral. Adding Azure Files would add network-filesystem behavior to
SQLite and complicate locking and recovery. Free App Service is also unsuitable for
an always-callable review because its free allowance is limited. A VM is the simplest
reliable match for this architecture.

## 1. Verify the student benefit before creating resources

1. Sign in to the [Azure portal](https://portal.azure.com/) and select the directory
   containing **Azure for Students**.
2. Open **Subscriptions > Azure for Students > Overview**. Confirm the subscription
   state is **Active** and record its credit expiry date.
3. Check the current balance in the
   [Microsoft Azure Sponsorships portal](https://www.microsoftazuresponsorships.com/).
   The offer currently provides $100 credit for 12 months and no credit card is
   required. Usage beyond included free quantities consumes that credit.
   For eligible new Azure customers, Microsoft currently lists 750 hours per month
   each of B1s, B2pts v2, and B2ats v2 burstable VMs for the first 12 months.
4. Keep the spending limit enabled. When all credit is consumed, Microsoft disables
   the student subscription and running services until the subscription is renewed or
   upgraded. Do not upgrade to pay-as-you-go merely to complete this assessment.
5. Open **Subscriptions > Azure for Students > Usage + quotas**, select a candidate
   region, and confirm at least one B-family vCPU is available. Quota and physical
   capacity are separate; a VM size can be unavailable even when quota remains.
6. Open **Cost Management > Cost analysis** after deployment and check it daily during
   the review window. Budget alerts are useful but do not stop resources automatically.

The student offer includes free monthly amounts of eligible services only within its
published conditions. The 12-month free-service quantities apply to new Azure customers.
Azure Marketplace and third-party branded products cannot use the student credit.
The credit covers eligible Azure resources; it does not pay for Vapi, Gemini, ngrok,
or GitHub usage. Keep checking those providers' own free balances and limits separately.

The application itself does not call Azure APIs. Do not create an app registration,
service principal, client secret, or Azure access token for this deployment.

## 2. Create the VM in the Azure portal

Open **Virtual machines > Create > Azure virtual machine** and enter:

### Basics

| Setting | Value |
| --- | --- |
| Subscription | `Azure for Students` |
| Resource group | Create `rg-voice-patient-registration` |
| Virtual machine name | `vm-voice-patient-registration` |
| Region | Start with `East US`; use another region if B1s quota/capacity is unavailable |
| Availability options | `No infrastructure redundancy required` |
| Security type | `Standard` |
| Image | `Ubuntu Server 24.04 LTS - x64 Gen2`, published by Canonical |
| VM architecture | `x64` |
| Size | `Standard_B1s` |
| Run with Azure Spot discount | Disabled; Spot VMs may be evicted |
| Authentication type | `SSH public key` |
| Username | `azureuser` |
| SSH public key source | `Generate new key pair` |
| Key pair name | `voice-patient-registration-key` |
| Public inbound ports | `None` initially |

`Standard_B1s` is enough for one low-traffic demonstration API, but its 1 GiB RAM is
tight during image builds. This guide adds a 2 GiB swap file before building. If B1s
is unavailable, `Standard_B2ats_v2` is the preferred x64 fallback when your subscription
shows it as eligible. Avoid the Arm-based B2pts v2 unless every container image has
been verified for Arm. In all cases, inspect the portal's estimated cost before continuing.

### Disks

- Select a **managed**, persistent OS disk. Do not use an ephemeral OS disk.
- Choose **Standard SSD locally redundant storage (LRS)** to limit cost.
- A 30–32 GiB OS disk is sufficient for this assessment.
- Keep host encryption at the platform default unless your subscription offers another
  option without added cost.
- Decide whether **Delete with VM** matches your cleanup plan. Clearing it preserves
  the disk after VM deletion but the unattached disk continues consuming credit.

The application stores its database under `/opt/voice-patient-registration/data` on
this managed disk. A separate data disk is unnecessary for the assessment.

### Networking

1. Use the default virtual network and subnet created for the resource group.
2. Create a **Standard** public IP so you can administer the VM. Review its estimated
   cost because public IPv4 may consume some student credit.
3. Create a network security group named `nsg-voice-patient-registration`.
4. Add one inbound rule for TCP port 22 with **Source = My IP address**. Do not allow
   SSH from `Any` or `0.0.0.0/0`.
5. Do not open ports 80, 443, or 8000. ngrok creates an outbound HTTPS connection and
   the Compose file binds FastAPI to VM localhost.
6. Leave outbound Internet access enabled so the VM can install packages, pull images,
   connect to GitHub, and establish the ngrok tunnel.

On **Management**, leave automatic guest patching enabled. Do not enable auto-shutdown
during the review window because the phone agent must remain reachable. You can enable
it later to conserve credit.

Select **Review + create**, inspect the estimated hourly cost, then select **Create**.
Download the generated `.pem` private key exactly once and store it outside this
repository. Wait until the deployment completes, then copy the VM's public IP from
its Overview page.

## 3. Connect from Windows

Open PowerShell in the directory containing the downloaded key:

```powershell
ssh -i ".\voice-patient-registration-key.pem" azureuser@YOUR_AZURE_PUBLIC_IP
```

Accept the host fingerprint only after confirming the IP in the Azure portal. If
Windows reports that the key permissions are too open:

```powershell
icacls ".\voice-patient-registration-key.pem" /inheritance:r
icacls ".\voice-patient-registration-key.pem" /grant:r "$($env:USERNAME):(R)"
```

If SSH times out, check that the VM is running, the NSG permits port 22 from your
current public IP, and you are using username `azureuser`. If your ISP address changes,
update the NSG source rather than widening it to the whole Internet.

## 4. Add swap and install Docker

Run these commands inside the Azure VM. The swap file prevents a B1s VM from running
out of memory while building the Python image:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

Install Git and Docker from Docker's official Ubuntu repository:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
sudo docker compose version
```

Using `sudo docker` avoids giving the login account root-equivalent membership in the
Docker group.

## 5. Clone the private GitHub repository

Create a read-only deploy key on the VM:

```bash
ssh-keygen -t ed25519 -C "voice-registration-azure-vm" \
  -f ~/.ssh/voice-registration-deploy -N ""
cat ~/.ssh/voice-registration-deploy.pub
```

Copy only the displayed public key. In GitHub, open the private repository and select
**Settings > Deploy keys > Add deploy key**. Leave write access disabled.

Configure SSH and clone the repository:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/voice-registration-deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config ~/.ssh/voice-registration-deploy
ssh -T git@github.com
sudo install -d -m 0755 -o azureuser -g azureuser /opt/voice-patient-registration
git clone git@github.com:YOUR_ACCOUNT/YOUR_PRIVATE_REPOSITORY.git \
  /opt/voice-patient-registration
cd /opt/voice-patient-registration
```

Confirm GitHub's host-key prompt. Never place a GitHub token in a clone URL. If the
private repository is not ready, use `scp` to copy the source while excluding `.env`,
`.venv`, `data`, caches, and `.local`.

## 6. Configure the Azure VM environment

Create the server environment file privately:

```bash
cd /opt/voice-patient-registration
cp .env.example .env
nano .env
```

Follow [`docs/SETUP_CREDENTIALS.md`](../docs/SETUP_CREDENTIALS.md). Generate different
production values for `API_KEY` and `VAPI_WEBHOOK_SECRET`, for example:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Run that command twice and use a different output for each secret. Also set:

```dotenv
DATABASE_URL=sqlite:////app/data/patients.db
GEMINI_MODEL=gemini-3.5-flash
NGROK_DOMAIN=YOUR_ASSIGNED_NGROK_HOSTNAME
PUBLIC_BASE_URL=https://YOUR_ASSIGNED_NGROK_HOSTNAME
```

Enter the Vapi, Gemini, ngrok, and Vapi webhook credential settings. Then protect the
file and create the bind-mounted database directory owned by container user `10001`:

```bash
chmod 600 .env
sudo install -d -m 0750 -o 10001 -g 10001 data
sudo docker compose config --quiet
```

The `--quiet` check validates Compose without expanding secrets into terminal logs.

## 7. Start FastAPI and ngrok

Start the API and check it from inside the VM:

```bash
sudo docker compose up --build -d api
sudo docker compose ps
curl --fail http://127.0.0.1:8000/health
sudo docker compose logs --tail 50 api
```

Stop the laptop's ngrok process with Ctrl+C before moving the same assigned domain to
Azure. Start the tunnel container:

```bash
sudo docker compose --profile public up -d
sudo docker compose ps
sudo docker compose logs --tail 50 ngrok
```

From your own computer, verify the public address:

```powershell
Invoke-RestMethod https://YOUR_ASSIGNED_NGROK_HOSTNAME/health
uv run python -m scripts.check_api --base-url https://YOUR_ASSIGNED_NGROK_HOSTNAME
```

The expected health response has `data.status` equal to `ok`. The VM's public IP is
used only for SSH; the reviewer uses the stable assigned ngrok HTTPS hostname.

## 8. Point Vapi at Azure

The Vapi custom bearer credential must contain the Azure VM's
`VAPI_WEBHOOK_SECRET`. If the server uses a new secret, update or recreate the Vapi
custom credential and place its credential ID in both server and local `.env` files.

With `PUBLIC_BASE_URL` set to the ngrok URL, run locally:

```powershell
uv run python -m scripts.preflight --online
uv run python -m scripts.configure_vapi
uv run python -m scripts.configure_vapi --apply
```

The last command creates or updates the assistant and requests only Vapi's free-number
provider. Confirm the assistant uses Google Gemini, Deepgram Nova-3, Deepgram Asteria,
and `https://YOUR_ASSIGNED_NGROK_HOSTNAME/vapi/webhook`.

## 9. Prove persistence

1. Complete a real call using fictional demographics and keep the patient UUID.
2. Retrieve it through the authenticated API.
3. Restart the API and retrieve the same UUID:

   ```bash
   cd /opt/voice-patient-registration
   sudo docker compose restart api
   curl --fail http://127.0.0.1:8000/health
   ```

4. Reboot from the Azure portal or run `sudo reboot`. Wait for the VM to return, SSH
   again, and verify both containers:

   ```bash
   cd /opt/voice-patient-registration
   sudo docker compose ps
   sudo docker compose logs --tail 50 api ngrok
   ```

5. Retrieve the original UUID through ngrok and make a second real call. Confirm both
   records remain available.

Docker starts at boot and Compose uses `restart: unless-stopped`, so existing containers
return after reboot. A stop/deallocate operation preserves the managed disk but makes
the service unavailable until the VM starts again.

## 10. Back up, update, and control cost

Back up SQLite before application updates:

```bash
cd /opt/voice-patient-registration
sudo docker compose exec api python -m scripts.backup_db \
  --destination /app/data/patients-backup-before-update.db
git pull --ff-only
sudo docker compose --profile public up --build -d
```

Choose a new backup name each time and copy important backups off the VM privately.
Monitor `/health`, `docker compose ps`, disk usage, Vapi balance, and Azure Cost
Management during the review window. VM compute, managed disk, public IPv4, and outbound
data transfer can be separate usage meters even when the VM itself has a free allowance.

After review, use **Stop** in the Azure portal and confirm the VM reaches
**Stopped (deallocated)** to stop compute consumption. Managed disks and public IPs may
still consume credit. Delete the resource group only after retaining any required
backup; deleting it permanently removes the VM, disk, IP, NSG, and database.

## Official references

- [Azure for Students benefits and free-service amounts](https://azure.microsoft.com/en-us/free/students)
- [Azure for Students disabled subscription and credit checks](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/azurestudents-subscription-disabled)
- [Azure spending-limit behavior](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit)
- [Azure VM quotas and regional capacity](https://learn.microsoft.com/en-us/azure/virtual-machines/quotas)
- [Connect to a Linux VM using SSH](https://learn.microsoft.com/en-us/azure/virtual-machines/linux-vm-connect)
- [Docker Engine installation on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
