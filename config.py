# Configuracoes do projeto Automacao Residencial M2.
# Wokwi usa esta rede padrao para liberar WiFi no ESP32 simulado.

WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "casa"
MQTT_TOPIC_PUB = "casa/data"
MQTT_CLIENT_ID = "esp32_smart_home_m2"

HTTP_PORT = 80

READ_INTERVAL_MS = 2000
MQTT_INTERVAL_MS = 5000
MQTT_RECONNECT_MS = 10000

# Ajuste conforme a leitura do LDR no simulador.
# No dashboard, observe "Luminosidade" e ajuste o limite se necessario.
LDR_DARK_THRESHOLD = 1800

# Rele liga automaticamente quando a temperatura chegar neste limite.
TEMP_RELAY_THRESHOLD_C = 28

AUTO_MODE_DEFAULT = True

# Nao coloque tokens reais em repositorios publicos.
BLYNK_AUTH_TOKEN = "SUBSTITUA_PELO_TOKEN_DO_BLYNK_SE_FOR_USAR"
