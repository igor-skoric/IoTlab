// Canonical copy: see docs/shelly_plus_uni.js
// IoT Lab reporter for Shelly Plus Uni + DS18B20
// Confirmed component: temperature:100
//
// Paste this into Shelly UI → Scripts → Create, set the three variables,
// then Start. Watch the script console for HTTP 201.
//
// Timestamp handling:
// Shelly Script has no Date() object. If Sys.unixtime is synced (NTP),
// measured_at is sent as UTC ISO-8601. If the clock is not synced yet,
// measured_at is omitted and Django stores server receive time instead.
// received_at is always set by Django.
//
// Offline buffer is NOT implemented. A failed POST is logged and the next
// live reading is attempted on the following interval.

var API_URL = "https://YOUR_DOMAIN/api/v1/telemetry/";
var API_KEY = "YOUR_DEVICE_API_KEY";
var DEVICE_INTERVAL_SECONDS = 60;

var TEMPERATURE_ID = 100;
// Leave null for Let's Encrypt / public CA. Use "*" only for self-signed HTTPS.
var SSL_CA = null;

var seq = 0;
var inFlight = false;

function pad2(n) {
  if (n < 10) {
    return "0" + JSON.stringify(n);
  }
  return JSON.stringify(n);
}

function isLeapYear(year) {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function unixToIsoUtc(unix) {
  var days = Math.floor(unix / 86400);
  var rem = Math.floor(unix - days * 86400);
  var hours = Math.floor(rem / 3600);
  rem = rem - hours * 3600;
  var mins = Math.floor(rem / 60);
  var secs = rem - mins * 60;
  var year = 1970;
  while (true) {
    var daysInYear = isLeapYear(year) ? 366 : 365;
    if (days < daysInYear) {
      break;
    }
    days = days - daysInYear;
    year = year + 1;
  }
  var md = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (isLeapYear(year)) {
    md[1] = 29;
  }
  var month = 0;
  while (days >= md[month]) {
    days = days - md[month];
    month = month + 1;
  }
  return (
    JSON.stringify(year) +
    "-" +
    pad2(month + 1) +
    "-" +
    pad2(days + 1) +
    "T" +
    pad2(hours) +
    ":" +
    pad2(mins) +
    ":" +
    pad2(secs) +
    "Z"
  );
}

function nextReadingUid(unix) {
  seq = seq + 1;
  var info = Shelly.getDeviceInfo();
  var prefix = "shelly";
  if (info && info.id) {
    prefix = info.id;
  }
  var stamp = unix;
  if (!stamp) {
    var sys = Shelly.getComponentStatus("Sys");
    if (sys && sys.uptime) {
      stamp = sys.uptime;
    } else {
      stamp = seq;
    }
  }
  return prefix + "-" + JSON.stringify(stamp) + "-" + JSON.stringify(seq);
}

function sendTelemetry(temperatureC, measuredAt, readingUid) {
  var payload = {
    reading_uid: readingUid,
    sensor_uid: "temperature:" + JSON.stringify(TEMPERATURE_ID),
    type: "temperature",
    value: temperatureC,
    unit: "C"
  };
  if (measuredAt) {
    payload.measured_at = measuredAt;
  }

  var body = JSON.stringify(payload);
  var request = {
    method: "POST",
    url: API_URL,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY
    },
    body: body,
    timeout: 10
  };
  if (SSL_CA) {
    request.ssl_ca = SSL_CA;
  }

  inFlight = true;
  Shelly.call(
    "HTTP.Request",
    request,
    function (result, error_code, error_message) {
      inFlight = false;
      if (error_code !== 0) {
        print("IoT Lab: network/HTTP error", error_code, error_message);
        return;
      }
      if (!result) {
        print("IoT Lab: empty HTTP result");
        return;
      }
      print("IoT Lab: HTTP", result.code, result.body);
    }
  );
}

function readAndSend() {
  if (inFlight) {
    print("IoT Lab: previous request still in flight, skipping this interval");
    return;
  }

  try {
    var sys = Shelly.getComponentStatus("Sys");
    var unix = 0;
    if (sys && sys.unixtime && sys.unixtime > 1000000000) {
      unix = sys.unixtime;
    }
    var measuredAt = unix ? unixToIsoUtc(unix) : null;
    if (!measuredAt) {
      print("IoT Lab: Shelly clock not synced; Django will set measured_at from server time");
    }

    Shelly.call(
      "Temperature.GetStatus",
      { id: TEMPERATURE_ID },
      function (status, error_code, error_message) {
        if (error_code !== 0) {
          print("IoT Lab: temperature read failed", error_code, error_message);
          return;
        }
        if (!status || status.tC === null || typeof status.tC === "undefined") {
          print("IoT Lab: no tC value from temperature:" + JSON.stringify(TEMPERATURE_ID));
          return;
        }
        sendTelemetry(status.tC, measuredAt, nextReadingUid(unix));
      }
    );
  } catch (e) {
    inFlight = false;
    print("IoT Lab: script error", e);
  }
}

Timer.set(DEVICE_INTERVAL_SECONDS * 1000, true, readAndSend);
readAndSend();
