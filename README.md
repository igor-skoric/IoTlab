# IoT Lab

Temporary Django platform for testing IoT devices and sensor telemetry (Shelly, ESP32, LILYGO, DS18B20, and later humidity/door/leak sensors).

It is intentionally small: ingest telemetry over HTTP, inspect it in admin and a simple dashboard. No MQTT, Celery, tenants, or HACCP.

## Stack

- Python 3.12+, Django, Django REST Framework
- PostgreSQL in Docker / production (SQLite works for a local venv)
- Gunicorn, WhiteNoise, Nginx
- Device auth via `X-API-Key`

## First Shelly Test

Use this for the first live Plus Uni + DS18B20 (`temperature:100`) check.

1. Start the app (Docker or local venv) and open Django admin: `/admin/`
2. **Devices → Add device**
   - Name: `Fridge 1` (or any label)
   - Device uid: `shelly-plus-uni-01`
   - Device type: `Shelly`
   - Active: checked
3. Save. Copy the API key from the green success message, or open the device and click the **API key (copy)** field.
4. Open `docs/shelly_plus_uni.js` and set:

```javascript
var API_URL = "https://YOUR_DOMAIN/api/v1/telemetry/";
var API_KEY = "PASTE_THE_API_KEY";
var DEVICE_INTERVAL_SECONDS = 60;
```

LAN test example: `http://192.168.1.10:8000/api/v1/telemetry/` (keep the trailing slash).

5. On the Shelly: **Scripts → Create** → paste the file → **Start**. Console should log `IoT Lab: HTTP 201 ...`.
6. Verify:
   - Admin → **Telemetry readings** shows a new row
   - Dashboard `/` shows the device, latest value, `measured_at`, `received_at`
   - Device page `/devices/shelly-plus-uni-01/` lists the last readings
7. Optional: Admin → **Sensors** → change Name from `temperature:100` to `Fridge 1`. Leave `sensor_uid` as `temperature:100`.

If the POST fails, check `ALLOWED_HOSTS`, HTTPS certificate, and that `API_URL` ends with `/api/v1/telemetry/`.

## Local (Docker)

### 1. Create `.env`

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Generate a secret key and put it in `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Leave `DATABASE_URL` pointing at the `db` service (`postgres://iot_lab:iot_lab@db:5432/iot_lab`).

### 2. Build and start

```bash
docker compose up --build
```

App: http://localhost:8000  
Nginx (optional): http://localhost:8080  
Admin: http://localhost:8000/admin/  
Health: http://localhost:8000/health/

### 3. Migrations

```bash
docker compose exec web python manage.py migrate
```

### 4. Create a superuser

```bash
docker compose exec web python manage.py createsuperuser
```

### 5. Open admin and create a Device

1. Sign in at http://localhost:8000/admin/
2. **Devices → Devices → Add**
3. Example values:
   - Name: `Fridge 1`
   - Device uid: `shelly-plus-uni-01`
   - Device type: `Shelly`
   - Active: checked
4. Save.

### 6. Copy the API key

After the first save, Django shows a success message with the **full API key**. Copy it now. Later screens only show a masked value (`abcd1234…wxyz`).

### 7. Test POST with curl

```bash
curl -X POST http://localhost:8000/api/v1/telemetry/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_DEVICE_API_KEY" \
  -d '{
    "sensor_uid": "temperature:100",
    "type": "temperature",
    "value": 27.3,
    "unit": "C"
  }'
```

On Windows PowerShell use `curl.exe` (plain `curl` is an alias for `Invoke-WebRequest`):

```powershell
curl.exe -X POST http://localhost:8000/api/v1/telemetry/ -H "Content-Type: application/json" -H "X-API-Key: YOUR_DEVICE_API_KEY" -d "{\"sensor_uid\":\"temperature:100\",\"type\":\"temperature\",\"value\":27.3,\"unit\":\"C\"}"
```

Expected: HTTP 201 and `{"success": true, "reading_id": ..., "device": "shelly-plus-uni-01"}`.

Check the dashboard at http://localhost:8000/ and the device page at http://localhost:8000/devices/shelly-plus-uni-01/.

Latest readings API:

```bash
curl http://localhost:8000/api/v1/devices/shelly-plus-uni-01/latest/
```

### 8. Configure the Shelly script

Follow **First Shelly Test** above. The live script is [`docs/shelly_plus_uni.js`](docs/shelly_plus_uni.js).

## Local (venv, SQLite, no Docker)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

In `.env` set:

```
DJANGO_SETTINGS_MODULE=iot_lab.settings.development
DEBUG=true
DATABASE_URL=sqlite:///db.sqlite3
```

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Tests

```bash
docker compose exec web python manage.py test
```

Or locally against SQLite:

```bash
python manage.py test
```

## API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/telemetry/` | `X-API-Key` | Ingest one reading |
| `POST` | `/api/v1/telemetry/batch/` | `X-API-Key` | Ingest many readings (offline flush) |
| `GET` | `/api/v1/devices/<device_uid>/latest/` | none | Latest value per sensor |
| `GET` | `/health/` | none | App + database probe |
| `GET` | `/` | none | Dashboard |
| `GET` | `/devices/<device_uid>/` | none | Device page |

### Telemetry POST

Header: `X-API-Key: DEVICE_API_KEY`

```json
{
  "reading_uid": "550e8400-e29b-41d4-a716-446655440000",
  "sensor_uid": "temperature:100",
  "type": "temperature",
  "value": 27.3,
  "unit": "C",
  "measured_at": "2026-09-05T17:30:00+02:00"
}
```

- Invalid API key → **401**
- Inactive device → **403**
- `measured_at` = time the device took the sample. If omitted, server time is used. Django never overwrites a supplied `measured_at` with receive time.
- `received_at` is always set by the server when the row is stored
- `reading_uid` is optional today and unique per device when present. Retrying the same uid returns the existing row (`status: "duplicate"`, HTTP 200) instead of inserting again
- Sensor is created automatically from `device + sensor_uid`
- The full JSON body is stored on `raw_payload` (extra fields are kept)
- Optional `payload` object and `text_value` are accepted

### Batch POST (offline flush)

```json
{
  "readings": [
    {
      "reading_uid": "550e8400-e29b-41d4-a716-446655440000",
      "sensor_uid": "temperature:100",
      "type": "temperature",
      "value": 4.2,
      "unit": "C",
      "measured_at": "2026-09-05T12:00:00+02:00"
    },
    {
      "reading_uid": "550e8400-e29b-41d4-a716-446655440001",
      "sensor_uid": "temperature:100",
      "type": "temperature",
      "value": 4.3,
      "unit": "C",
      "measured_at": "2026-09-05T12:02:00+02:00"
    }
  ]
}
```

Each reading is validated on its own. A bad item is listed under `results` with `status: "rejected"` and does not roll back accepted rows.

Acknowledgement fields: `accepted`, `created`, `duplicates`, `rejected`, and per-item `status` (`created` / `duplicate` / `rejected`). A future device buffer should delete locally stored samples whose item status is `created` or `duplicate`.

HTTP: **201** if any row was created, **200** if the whole batch was already stored, **400** if nothing was accepted.

Device-side offline storage is **not** implemented yet. The API and `reading_uid` uniqueness are in place so that buffer can be added later.

## Production (Ubuntu VPS, Docker Compose, domain + HTTPS)

1. Point DNS A/AAAA records for `DOMAIN` at the VPS.
2. Install Docker Engine and the Compose plugin.
3. Copy this project to the server (git clone or `scp`).
4. Create `.env` from `.env.example` and set:

```
SECRET_KEY=...long random value...
DEBUG=false
ALLOWED_HOSTS=DOMAIN,www.DOMAIN
CSRF_TRUSTED_ORIGINS=https://DOMAIN,https://www.DOMAIN
DJANGO_SETTINGS_MODULE=iot_lab.settings.production
DATABASE_URL=postgres://iot_lab:STRONG_PASSWORD@db:5432/iot_lab
POSTGRES_PASSWORD=STRONG_PASSWORD
```

5. Keep Gunicorn off the public internet. In `docker-compose.yml`, change the web ports to `127.0.0.1:8000:8000` (or drop the `nginx` service and use host Nginx only).
6. Start the stack:

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

7. Install Nginx and Certbot on the host:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

8. Copy `deploy/nginx.host-https.conf.example` to `/etc/nginx/sites-available/iot_lab`, replace `DOMAIN`, enable the site, then:

```bash
sudo certbot --nginx -d DOMAIN
sudo nginx -t && sudo systemctl reload nginx
```

9. Confirm:

```bash
curl -s https://DOMAIN/health/
```

10. Create the Shelly device in admin, copy the API key, install the script with `https://DOMAIN/api/v1/telemetry/`.

Production curl:

```bash
curl -X POST https://DOMAIN/api/v1/telemetry/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_DEVICE_API_KEY" \
  -d '{
    "sensor_uid": "temperature:100",
    "type": "temperature",
    "value": 27.3,
    "unit": "C"
  }'
```

Gunicorn is configured in `gunicorn.conf.py` (3 workers, bind `0.0.0.0:8000`). Static files are collected on container start and served by WhiteNoise through Gunicorn/Nginx.

## cPanel / shared hosting (no Docker)

This app can run on a normal cPanel Python App (Phusion Passenger) without Docker. Shared hosting is fine for a lab with a few devices; it is not a high-throughput setup.

1. Create a Python application in cPanel (Python 3.12 if available).
2. Upload this project into the app directory (git clone or zip).
3. In the virtualenv:

```bash
pip install -r requirements.txt
```

4. Create `.env` in the project root:

```
SECRET_KEY=...long random value...
DEBUG=false
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
DJANGO_SETTINGS_MODULE=iot_lab.settings.production
DATABASE_URL=sqlite:///db.sqlite3
```

SQLite is the simplest option on shared hosting. Put `db.sqlite3` in a writable directory and back it up. PostgreSQL/MySQL are optional if the host provides them; this project already understands `DATABASE_URL`.

5. Point the cPanel app startup file at `passenger_wsgi.py` (already in the repo).
6. SSH or cPanel terminal:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

7. Enable HTTPS with AutoSSL / cPanel SSL. Set `CSRF_TRUSTED_ORIGINS` to the `https://` origin.
8. Confirm `https://yourdomain.com/health/` returns `{"status": "ok", ...}`.
9. Create the Shelly device in admin and set `API_URL` to `https://yourdomain.com/api/v1/telemetry/`.

Notes:

- Passenger may idle the process; the first request after idle can be slow.
- WhiteNoise serves `/static/` through Django; you do not need a separate static mapping.
- Keep `DEBUG=false`. Do not commit `.env`.
- If Passenger looks for `passenger_wsgi.py` one directory up, copy or symlink it to the app root cPanel created.

## Project layout

```
devices/          Device + Sensor models, dashboard views, admin
telemetry/        TelemetryReading, ingest API, latest API
iot_lab/settings/ development + production settings
docs/shelly_plus_uni.js   Shelly Plus Uni live script
passenger_wsgi.py cPanel / Passenger entry
deploy/           Nginx examples
```

Out of scope on purpose: MQTT, device-side offline buffering (API is ready), Celery/Redis, users/tenants/companies, HACCP, charts.
