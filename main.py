import time

import dht
import network
import socket
from machine import ADC, I2C, PWM, Pin, time_pulse_us

try:
    import ujson as json
except ImportError:
    import json

import config
from ssd1306 import SSD1306_I2C
from umqtt.simple import MQTTClient


# Projeto: Automacao Residencial M2 - Wokwi + ESP32 + MicroPython
# Pinagem sincronizada com diagram.json.


PIN_DHT = 15
PIN_PIR = 13
PIN_LDR = 34
PIN_TRIG = 5
PIN_ECHO = 18
PIN_LED = 2
PIN_RELAY = 4
PIN_BUZZER = 14
PIN_SERVO = 12
PIN_I2C_SDA = 21
PIN_I2C_SCL = 22

READ_INTERVAL_MS = getattr(config, "READ_INTERVAL_MS", 2000)
MQTT_INTERVAL_MS = getattr(config, "MQTT_INTERVAL_MS", 5000)
MQTT_RECONNECT_MS = getattr(config, "MQTT_RECONNECT_MS", 10000)
HTTP_PORT = getattr(config, "HTTP_PORT", 80)

LDR_DARK_THRESHOLD = getattr(config, "LDR_DARK_THRESHOLD", 1800)
TEMP_RELAY_THRESHOLD_C = getattr(config, "TEMP_RELAY_THRESHOLD_C", 28)
AUTO_MODE_DEFAULT = getattr(config, "AUTO_MODE_DEFAULT", True)


dht_sensor = dht.DHT22(Pin(PIN_DHT))
pir = Pin(PIN_PIR, Pin.IN)

ldr = ADC(Pin(PIN_LDR))
ldr.atten(ADC.ATTN_11DB)

trig = Pin(PIN_TRIG, Pin.OUT)
echo = Pin(PIN_ECHO, Pin.IN)

led = Pin(PIN_LED, Pin.OUT)
relay = Pin(PIN_RELAY, Pin.OUT)
buzzer = Pin(PIN_BUZZER, Pin.OUT)
servo = PWM(Pin(PIN_SERVO), freq=50)

oled = None
try:
    i2c = I2C(0, scl=Pin(PIN_I2C_SCL), sda=Pin(PIN_I2C_SDA))
    oled = SSD1306_I2C(128, 64, i2c)
except Exception as exc:
    print("OLED desabilitado:", exc)


state = {
    "temp": None,
    "humidity": None,
    "distance_cm": None,
    "light": 0,
    "motion": False,
    "led": 0,
    "relay": 0,
    "buzzer": 0,
    "servo_angle": 90,
    "auto_mode": AUTO_MODE_DEFAULT,
    "wifi_ip": "",
    "mqtt": "offline",
    "last_error": "",
}


def ticks_due(last_tick, interval_ms):
    return time.ticks_diff(time.ticks_ms(), last_tick) >= interval_ms


def to_bytes(value):
    if isinstance(value, bytes):
        return value
    return str(value).encode()


def set_last_error(message):
    state["last_error"] = str(message)
    print("ERRO:", state["last_error"])


def set_servo(angle):
    try:
        numeric_angle = int(angle)
    except Exception:
        numeric_angle = 0

    numeric_angle = max(0, min(180, numeric_angle))
    # MicroPython ESP32 PWM.duty usa escala 0..1023.
    # Para servo SG90 em 50 Hz, uma faixa pratica simulada fica em torno de 26..128.
    duty = int(26 + ((numeric_angle / 180) * 102))
    servo.duty(duty)
    state["servo_angle"] = numeric_angle


def set_output(name, value):
    pin_value = 1 if str(value).lower() in ("1", "true", "on", "ligar", "sim") else 0

    if name == "led":
        led.value(pin_value)
        state["led"] = led.value()
    elif name in ("relay", "rele"):
        relay.value(pin_value)
        state["relay"] = relay.value()
    elif name == "buzzer":
        buzzer.value(pin_value)
        state["buzzer"] = buzzer.value()


def get_distance_cm():
    trig.off()
    time.sleep_us(2)
    trig.on()
    time.sleep_us(10)
    trig.off()

    try:
        duration = time_pulse_us(echo, 1, 30000)
    except OSError:
        return None

    if duration < 0:
        return None

    return round((duration * 0.0343) / 2, 1)


def connect_wifi(timeout_s=25):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Conectando ao WiFi '{}'...".format(config.WIFI_SSID))
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

        started_at = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), started_at) > timeout_s * 1000:
                set_last_error("Timeout conectando ao WiFi")
                return None
            time.sleep_ms(300)

    ip_address = wlan.ifconfig()[0]
    state["wifi_ip"] = ip_address
    print("WiFi conectado:", ip_address)
    return wlan


def mqtt_callback(topic, message):
    topic_text = topic.decode() if isinstance(topic, bytes) else str(topic)
    message_text = message.decode().strip().lower() if isinstance(message, bytes) else str(message).strip().lower()

    print("MQTT RX:", topic_text, message_text)

    command = topic_text.rsplit("/", 1)[-1]

    if command == "led":
        state["auto_mode"] = False
        set_output("led", message_text)
    elif command in ("relay", "rele"):
        state["auto_mode"] = False
        set_output("relay", message_text)
    elif command == "buzzer":
        state["auto_mode"] = False
        set_output("buzzer", message_text)
    elif command == "servo":
        set_servo(message_text)
    elif command == "auto":
        state["auto_mode"] = message_text in ("1", "true", "on", "ligar", "sim")


def connect_mqtt():
    try:
        client = MQTTClient(
            client_id=to_bytes(config.MQTT_CLIENT_ID),
            server=config.MQTT_BROKER,
            port=getattr(config, "MQTT_PORT", 1883),
            keepalive=30,
        )
        client.set_callback(mqtt_callback)
        client.connect()

        prefix = getattr(config, "MQTT_TOPIC_PREFIX", "casa")
        topics = (
            "{}/cmd/led".format(prefix),
            "{}/cmd/relay".format(prefix),
            "{}/cmd/rele".format(prefix),
            "{}/cmd/buzzer".format(prefix),
            "{}/cmd/servo".format(prefix),
            "{}/cmd/auto".format(prefix),
            "casa/led",
            "casa/rele",
            "casa/buzzer",
            "casa/servo",
        )
        for topic in topics:
            client.subscribe(to_bytes(topic))

        state["mqtt"] = "online"
        print("MQTT conectado:", config.MQTT_BROKER)
        return client
    except Exception as exc:
        state["mqtt"] = "offline"
        set_last_error("MQTT indisponivel: {}".format(exc))
        return None


def read_sensors():
    try:
        dht_sensor.measure()
        state["temp"] = dht_sensor.temperature()
        state["humidity"] = dht_sensor.humidity()
    except Exception as exc:
        set_last_error("Falha DHT22: {}".format(exc))

    try:
        state["light"] = ldr.read()
    except Exception as exc:
        set_last_error("Falha LDR: {}".format(exc))

    state["motion"] = bool(pir.value())
    state["distance_cm"] = get_distance_cm()


def apply_automation():
    if not state["auto_mode"]:
        state["led"] = led.value()
        state["relay"] = relay.value()
        state["buzzer"] = buzzer.value()
        return

    dark = state["light"] < LDR_DARK_THRESHOLD
    motion = bool(state["motion"])

    # Iluminacao e alarme: liga quando ha movimento em baixa luminosidade.
    set_output("led", dark and motion)
    set_output("buzzer", dark and motion)

    # Rele como simulacao de carga/ventilacao quando temperatura passa do limite.
    temp = state["temp"]
    set_output("relay", temp is not None and temp >= TEMP_RELAY_THRESHOLD_C)


def status_payload():
    return {
        "temp": state["temp"],
        "humidity": state["humidity"],
        "distance_cm": state["distance_cm"],
        "light": state["light"],
        "motion": state["motion"],
        "led": led.value(),
        "relay": relay.value(),
        "buzzer": buzzer.value(),
        "servo_angle": state["servo_angle"],
        "auto_mode": state["auto_mode"],
        "wifi_ip": state["wifi_ip"],
        "mqtt": state["mqtt"],
        "uptime_ms": time.ticks_ms(),
        "last_error": state["last_error"],
    }


def publish_status(client):
    if client is None:
        return client

    try:
        payload = json.dumps(status_payload())
        client.publish(to_bytes(config.MQTT_TOPIC_PUB), to_bytes(payload))
        print("MQTT TX {}: {}".format(config.MQTT_TOPIC_PUB, payload))
        return client
    except Exception as exc:
        state["mqtt"] = "offline"
        set_last_error("Falha publicando MQTT: {}".format(exc))
        try:
            client.disconnect()
        except Exception:
            pass
        return None


def update_oled():
    if oled is None:
        return

    try:
        oled.fill(0)
        oled.text("Automacao M2", 0, 0)
        oled.text("T: {}C U:{}%".format(state["temp"], state["humidity"]), 0, 12)

        distance = state["distance_cm"]
        if distance is None:
            oled.text("Dist: timeout", 0, 24)
        else:
            oled.text("Dist: {}cm".format(distance), 0, 24)

        oled.text("Luz: {}".format(state["light"]), 0, 36)
        oled.text("Mov: {}".format("SIM" if state["motion"] else "NAO"), 0, 48)
        oled.show()
    except Exception as exc:
        set_last_error("Falha OLED: {}".format(exc))


def html_escape(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dashboard_html():
    payload = status_payload()
    distance = payload["distance_cm"]
    distance_text = "sem leitura" if distance is None else "{} cm".format(distance)

    return """<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Automacao Residencial M2</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; background: #f6f7fb; color: #1f2937; }}
    h1 {{ margin-bottom: 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card {{ background: white; border: 1px solid #ddd; border-radius: 10px; padding: 14px; box-shadow: 0 1px 3px #ddd; }}
    .value {{ font-size: 1.4rem; font-weight: bold; }}
    a.button {{ display: inline-block; padding: 10px 12px; margin: 4px 2px; background: #2563eb; color: white; text-decoration: none; border-radius: 6px; }}
    a.off {{ background: #6b7280; }}
    code {{ background: #eee; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Automacao Residencial M2</h1>
  <p>IP: <code>{wifi_ip}</code> | MQTT: <strong>{mqtt}</strong> | Modo automatico: <strong>{auto}</strong></p>

  <div class="grid">
    <div class="card"><div>Temperatura</div><div class="value">{temp} C</div></div>
    <div class="card"><div>Umidade</div><div class="value">{humidity}%</div></div>
    <div class="card"><div>Distancia</div><div class="value">{distance}</div></div>
    <div class="card"><div>Luminosidade</div><div class="value">{light}</div></div>
    <div class="card"><div>Movimento</div><div class="value">{motion}</div></div>
    <div class="card"><div>Servo</div><div class="value">{servo} graus</div></div>
  </div>

  <h2>Comandos</h2>
  <p>
    <a class="button" href="/auto/on">AUTO ON</a>
    <a class="button off" href="/auto/off">AUTO OFF</a>
  </p>
  <p>
    <a class="button" href="/led/on">LED ON</a>
    <a class="button off" href="/led/off">LED OFF</a>
    <a class="button" href="/rele/on">RELE ON</a>
    <a class="button off" href="/rele/off">RELE OFF</a>
    <a class="button" href="/buzzer/on">BUZZER ON</a>
    <a class="button off" href="/buzzer/off">BUZZER OFF</a>
  </p>
  <p>
    Servo:
    <a class="button" href="/servo/0">0</a>
    <a class="button" href="/servo/90">90</a>
    <a class="button" href="/servo/180">180</a>
  </p>

  <p>API JSON: <code>/api/status</code></p>
  <p>Ultimo erro: {last_error}</p>
</body>
</html>""".format(
        wifi_ip=html_escape(payload["wifi_ip"]),
        mqtt=html_escape(payload["mqtt"]),
        auto="ON" if payload["auto_mode"] else "OFF",
        temp=html_escape(payload["temp"]),
        humidity=html_escape(payload["humidity"]),
        distance=html_escape(distance_text),
        light=html_escape(payload["light"]),
        motion="SIM" if payload["motion"] else "NAO",
        servo=html_escape(payload["servo_angle"]),
        last_error=html_escape(payload["last_error"]),
    )


def http_response(conn, body, content_type="text/html; charset=utf-8", status="200 OK"):
    if isinstance(body, str):
        body_bytes = body.encode()
    else:
        body_bytes = body

    headers = (
        "HTTP/1.1 {}\r\n"
        "Content-Type: {}\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n\r\n"
    ).format(status, content_type, len(body_bytes))

    conn.send(headers.encode())
    conn.send(body_bytes)


def parse_path(request):
    try:
        first_line = request.split("\r\n", 1)[0]
        return first_line.split(" ")[1]
    except Exception:
        return "/"


def handle_route(path):
    if path == "/led/on":
        state["auto_mode"] = False
        set_output("led", "on")
    elif path == "/led/off":
        state["auto_mode"] = False
        set_output("led", "off")
    elif path == "/rele/on":
        state["auto_mode"] = False
        set_output("relay", "on")
    elif path == "/rele/off":
        state["auto_mode"] = False
        set_output("relay", "off")
    elif path == "/buzzer/on":
        state["auto_mode"] = False
        set_output("buzzer", "on")
    elif path == "/buzzer/off":
        state["auto_mode"] = False
        set_output("buzzer", "off")
    elif path == "/auto/on":
        state["auto_mode"] = True
    elif path == "/auto/off":
        state["auto_mode"] = False
    elif path.startswith("/servo/"):
        set_servo(path.rsplit("/", 1)[-1])


def start_http_server():
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        server.bind(("0.0.0.0", HTTP_PORT))
        server.listen(3)
        server.setblocking(False)
        print("Servidor HTTP pronto na porta {}.".format(HTTP_PORT))
        return server
    except Exception as exc:
        set_last_error("HTTP desabilitado: {}".format(exc))
        return None


def handle_http(server):
    if server is None:
        return

    try:
        conn, addr = server.accept()
    except OSError:
        return

    try:
        try:
            conn.settimeout(2)
        except Exception:
            pass

        request = conn.recv(1024).decode()
        path = parse_path(request)
        handle_route(path)

        if path == "/api/status":
            http_response(conn, json.dumps(status_payload()), "application/json; charset=utf-8")
        else:
            http_response(conn, dashboard_html())

        print("HTTP {} {}".format(addr, path))
    except Exception as exc:
        set_last_error("Falha HTTP: {}".format(exc))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    print("Iniciando Automacao Residencial M2...")
    set_servo(state["servo_angle"])

    wlan = connect_wifi()
    server = start_http_server() if wlan is not None else None
    client = connect_mqtt() if wlan is not None else None

    last_read = time.ticks_ms() - READ_INTERVAL_MS
    last_mqtt = time.ticks_ms() - MQTT_INTERVAL_MS
    last_reconnect = time.ticks_ms()

    while True:
        handle_http(server)

        if ticks_due(last_read, READ_INTERVAL_MS):
            read_sensors()
            apply_automation()
            update_oled()
            print("STATUS:", status_payload())
            last_read = time.ticks_ms()

        if client is not None:
            try:
                client.check_msg()
            except Exception as exc:
                state["mqtt"] = "offline"
                set_last_error("Falha lendo MQTT: {}".format(exc))
                try:
                    client.disconnect()
                except Exception:
                    pass
                client = None

        if wlan is not None and client is None and ticks_due(last_reconnect, MQTT_RECONNECT_MS):
            client = connect_mqtt()
            last_reconnect = time.ticks_ms()

        if client is not None and ticks_due(last_mqtt, MQTT_INTERVAL_MS):
            client = publish_status(client)
            last_mqtt = time.ticks_ms()

        time.sleep_ms(25)


try:
    main()
except KeyboardInterrupt:
    print("Programa interrompido pelo usuario.")
except Exception as exc:
    set_last_error("Falha fatal: {}".format(exc))
    raise
