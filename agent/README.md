# PreventaB Remote Agent

This folder contains the remote device agent for macOS and Ubuntu/Linux.

The agent sends:

- CPU usage
- RAM usage
- Disk usage
- Available OS log events

to the Django server using the ingest endpoint.

---

## Files

- `os_agent.py` — remote agent script
- `.env.example` — example environment file for the remote device

---

## Supported systems

- macOS
- Ubuntu / Linux

---

## What you need before running

1. Django server must already be running
2. A device must exist in the web app
3. You must copy the device API key
4. The remote machine must know the server URL
5. The remote machine must have Python 3 installed

---

## Step 1 — Copy files to the remote machine

Copy these files to the macOS or Ubuntu machine:

- `agent/os_agent.py`
- `agent/.env.example`

Rename the env file:

```bash
cp .env.example .env
```

---

## Step 2 — Create a virtual environment

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install psutil requests python-dotenv
```

### Ubuntu

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install psutil requests python-dotenv
```

If `venv` is missing on Ubuntu:

```bash
sudo apt update
sudo apt install python3-venv -y
```

---

## Step 3 — Update `.env`

Edit `.env` and fill in:

- `SERVER_URL`
- `DEVICE_API_KEY`
- `AGENT_INGEST_TOKEN`

### Example using same Wi-Fi IP

```env
SERVER_URL=http://192.168.1.100:8000
DEVICE_API_KEY=replace-with-device-api-key
AGENT_INGEST_TOKEN=replace-with-the-same-ingest-token
INTERVAL_SECONDS=60
MAX_EVENTS=10
REQUEST_TIMEOUT_SECONDS=15
VERIFY_TLS=1
```

### Example using Cloudflare Quick Tunnel

```env
SERVER_URL=https://your-current-quick-tunnel.trycloudflare.com
DEVICE_API_KEY=replace-with-device-api-key
AGENT_INGEST_TOKEN=replace-with-the-same-ingest-token
INTERVAL_SECONDS=60
MAX_EVENTS=10
REQUEST_TIMEOUT_SECONDS=15
VERIFY_TLS=1
```

Important:
If the Quick Tunnel URL changes, update `SERVER_URL` again.

---

## Step 4 — Run the agent

```bash
python3 os_agent.py
```

---

## How the data flows

```text
Remote device
  -> os_agent.py
  -> POST to /telemetry/agent/ingest/
  -> Django validates token and device key
  -> PostgreSQL stores data
  -> dashboards and alerts update
```

---

## Common problems

### Unauthorized / 401
Usually the ingest token is wrong.

Check:
- remote `.env` `AGENT_INGEST_TOKEN`
- server `.env` `AGENT_INGEST_TOKEN`

They must match exactly.

### Unknown device api_key
The API key does not match a device in Django.

Copy the device API key again from the app.

### Connection error
Check:
- Django server is running
- `SERVER_URL` is correct
- firewall is not blocking access
- internet/LAN access is available

### SSL / certificate error
If testing with HTTPS and there is a certificate issue, confirm the URL is correct first.
Only use `VERIFY_TLS=0` temporarily for troubleshooting.

### No logs on macOS or Linux
Some systems limit log access.
The agent can still send telemetry even if log access is partial.

---

## Recommended use

### Best for local network demo
Use same Wi-Fi with:

```env
SERVER_URL=http://YOUR_SERVER_IP:8000
```

### Best for phone/public testing
Use the current Cloudflare Quick Tunnel URL.

### Important
Quick Tunnel URLs are temporary.
When the tunnel stops, sleeps, or restarts, the URL usually changes.
Update the agent `.env` if that happens.
