<div align="center">

# 🛡️ PreventaB

### Explainable AI for Computer System Failure Prediction & Prevention

**Student:** Bibash Shrestha  
**Course:** BSc (Hons) Computing  
**Module:** Production Project (CRN 10810)  
**Institution:** The British College, Kathmandu

*A Django + PostgreSQL web application that collects device telemetry and OS logs, predicts system failure risk, explains the prediction, generates alerts, and supports cross-device testing with QR-based access.*

</div>

---

## Overview

PreventaB is a full-stack Django project for monitoring system health and predicting computer failure risk using explainable AI.

### Main features

- Django web application with admin and user dashboards
- PostgreSQL database backend
- Device management with API keys
- Telemetry collection for CPU, RAM, and disk usage
- OS log ingestion
- ML-based risk prediction with heuristic fallback
- Explainable AI summaries
- Alerts and notifications
- PDF report generation
- Local Windows collector
- Remote macOS/Linux agent support
- QR-based testing using Cloudflare Quick Tunnel

---

## Tech stack

- Python 3.10+
- Django 5
- PostgreSQL
- WhiteNoise
- scikit-learn
- joblib
- psutil
- requests
- ReportLab
- SHAP / LIME
- Django templates + static JS/CSS

---

## Project structure

```text
Product/
├── accounts/
├── alerts/
├── devices/
├── telemetry/
│   ├── management/commands/run_collector.py
│   └── services/
├── agent/
│   ├── os_agent.py
│   ├── .env.example
│   └── README.md
├── core/
├── ml_artifacts/
├── notebooks/
├── preventab/
├── static/
├── templates/
├── .env.example
├── manage.py
├── make_qr.py
├── requirements.txt
└── README.md
```

---

## How the system works

### Local Django server
The main Django application runs on the Windows laptop and connects to PostgreSQL on the same machine.

### Local collector
The Windows host can collect telemetry and logs directly using:

```bash
python manage.py run_collector --once --events 30
```

### Remote agent
A macOS or Ubuntu/Linux machine can run `agent/os_agent.py` and send telemetry/log data to the Django server.

### QR testing with Cloudflare Quick Tunnel
For testing on phone or other devices without same-Wi-Fi dependency:

1. Run Django locally
2. Run Cloudflare Quick Tunnel
3. Get the temporary public URL
4. Generate a QR code using `make_qr.py`
5. Scan the QR code on another device

---

## Runtime features used by the ML model

The model uses these features:

- `cpu`
- `ram`
- `disk`
- `critical_count_1h`
- `error_count_1h`
- `warning_count_1h`

### Risk levels

- **LOW**: score < 0.4
- **MEDIUM**: score >= 0.4
- **HIGH**: score >= 0.7

If the ML model cannot be loaded, the project falls back to a rule-based heuristic.

---

## Setup guide

## 1. Clone the repository

```bash
git clone <your-repo-url>
cd Product
```

---

## 2. Create and activate virtual environment

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows CMD

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Ubuntu

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. PostgreSQL setup

Create a database and user.

### Example psql commands

```sql
CREATE USER preventab_user WITH PASSWORD 'change_this_password';
CREATE DATABASE preventab OWNER preventab_user;
ALTER ROLE preventab_user SET client_encoding TO 'utf8';
ALTER ROLE preventab_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE preventab_user SET timezone TO 'Asia/Kathmandu';
GRANT ALL PRIVILEGES ON DATABASE preventab TO preventab_user;
\c preventab
GRANT ALL ON SCHEMA public TO preventab_user;
ALTER SCHEMA public OWNER TO preventab_user;
```

---

## 4. Create environment file

Copy the example file:

### Windows

```cmd
copy .env.example .env
```

### macOS / Ubuntu

```bash
cp .env.example .env
```

Then update the values in `.env`.

---

## 5. Apply migrations

```bash
python manage.py migrate
```

---

## 6. Create admin user

```bash
python manage.py createsuperuser
```

---

## 7. Collect static files

```bash
python manage.py collectstatic --noinput
```

---

## 8. Run Django locally

```bash
python manage.py runserver 127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/login/
```

---

## Environment variables

The project reads key settings from `.env`.

Important values include:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_TRUST_X_FORWARDED_PROTO`
- `PUBLIC_BASE_URL`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `AGENT_INGEST_TOKEN`
- `ML_*`

---

## Local Windows demo

### Run one collection cycle

```bash
python manage.py run_collector --once --events 30
```

### Run continuous collection

```bash
python manage.py run_collector
```

### Run with custom interval

```bash
python manage.py run_collector --interval 60 --events 30
```

---

## Cross-device testing with Cloudflare Quick Tunnel

This is useful when same Wi-Fi connectivity is unreliable.

### Step 1 — Run Django

```powershell
python manage.py runserver 127.0.0.1:8000
```

### Step 2 — Start Cloudflare tunnel

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare will generate a temporary public URL like:

```text
https://random-name.trycloudflare.com
```

### Step 3 — Generate QR code

```powershell
python make_qr.py https://random-name.trycloudflare.com
```

This creates:

```text
project_test_qr.png
```

### Step 4 — Scan from phone or another device

Open the QR image and scan it from mobile.

### Important note
Quick Tunnel URLs are temporary. If the laptop sleeps, restarts, or the `cloudflared` process stops, the tunnel usually ends and a new URL is generated next time.

When that happens:
- update `PUBLIC_BASE_URL` in `.env`
- rerun `make_qr.py`
- rescan the new QR code

---

## Remote agent setup

For macOS and Ubuntu/Linux remote devices, use the files inside `agent/`.

See:

- `agent/README.md`
- `agent/.env.example`

---

## Common commands

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver 127.0.0.1:8000
python manage.py run_collector --once --events 30
python manage.py run_collector --interval 60 --events 30
python make_qr.py https://your-current-tunnel-url.trycloudflare.com
```

---

## Troubleshooting

### Invalid HTTP_HOST header
Make sure `.env` includes:

```env
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,.trycloudflare.com
```

or include your LAN IP as well if needed.

### CSRF verification failed
Make sure `.env` includes:

```env
DJANGO_CSRF_TRUSTED_ORIGINS=https://*.trycloudflare.com
DJANGO_TRUST_X_FORWARDED_PROTO=1
```

### Static files not loading
Run:

```bash
python manage.py collectstatic --noinput
```

### Agent cannot connect
Check:
- `SERVER_URL`
- `DEVICE_API_KEY`
- `AGENT_INGEST_TOKEN`
- firewall
- Django server is running

### Database connection refused
Check:
- PostgreSQL service is running
- `.env` DB values are correct
- port 5432 is correct

---

## Security notes

- Never commit the real `.env`
- Never commit real email passwords, app passwords, or tokens
- Only commit `.env.example`
- Rotate secrets if they were ever shared
- Keep PostgreSQL local unless you intentionally deploy it elsewhere

---

## Files to commit

Track:

- `README.md`
- `.env.example`
- `agent/README.md`
- `agent/.env.example`
- `make_qr.py`
- source code and migrations

Do not track:

- `.env`
- `.venv/`
- `project_test_qr.png`
- `staticfiles/`
- personal secrets

---

## Final workflow summary

Recommended demo workflow:

- Windows laptop runs Django + PostgreSQL
- Optional local Windows collector runs via `run_collector`
- macOS/Ubuntu device can run `agent/os_agent.py`
- phone/device testing can use Cloudflare Quick Tunnel + QR code
