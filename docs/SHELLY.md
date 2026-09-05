# Shelly Plus Uni → IoT Lab

This lab expects a DS18B20 on a Shelly Plus Uni as component **`temperature:100`**.

The live script is [`docs/shelly_plus_uni.js`](shelly_plus_uni.js).

## First test

1. In Django admin, add a Device (`Shelly`, uid e.g. `shelly-plus-uni-01`).
2. Copy the API key (success message, copy field on the device, or the “Show full API keys” action).
3. Paste `docs/shelly_plus_uni.js` into **Scripts** on the Shelly.
4. Set `API_URL`, `API_KEY`, and `DEVICE_INTERVAL_SECONDS` (60).
5. Start the script and confirm `IoT Lab: HTTP 201` in the console.
6. Check `/admin/telemetry/telemetryreading/` and `/`.

After the first POST, rename the sensor **Name** to `Fridge 1`. Leave `sensor_uid` as `temperature:100`.

## Timestamp handling

Shelly Script cannot use `Date()`. If `Sys.unixtime` is NTP-synced, the script sends `measured_at` as UTC ISO-8601. If the clock is not ready, it omits `measured_at` and Django uses server time. `received_at` is always set by Django.

## TLS

- Let's Encrypt / public CA: leave `SSL_CA = null`.
- Self-signed lab certificate: set `SSL_CA = "*"`.
- HTTP on a LAN IP is fine for local tests, e.g. `http://192.168.1.10:8000/api/v1/telemetry/`.

The script does **not** buffer offline samples. If the network is down it logs an error and waits for the next interval.
