# Automacao Residencial M2 - Wokwi + MicroPython + VS Code

Leia primeiro: [`README_VSCODE.md`](README_VSCODE.md).

Esta versao foi ajustada para rodar no Wokwi for VS Code com MicroPython, incluindo:

- upload robusto sem depender do raw REPL do `mpremote`;
- dashboard HTTP em `http://localhost:8180`;
- MQTT em `casa/data`;
- comandos por HTTP e MQTT;
- tratamento de erro para DHT22, OLED, MQTT, HTTP e HC-SR04.

---

# Objective
The objective of this project is to design and simulate a Smart Home System that includes automated lighting, temperature control, and a security alarm using IoT principles with Wokwi. The system leverages an ESP32 microcontroller to collect data from various sensors, control actuators, and interact with Blynk and MQTT for remote monitoring and control.

# Features
Automated Lighting Control:
Based on light intensity (LDR sensor) and motion detection (PIR sensor).
Temperature and Humidity Control:
Monitors the environment using a DHT22 sensor.
Security Alarm:
Activates a buzzer when motion is detected in a low-light environment.
Remote Monitoring:
Integrates with Blynk for real-time control of LEDs and buzzer.
MQTT Integration:
Publishes sensor data to an MQTT broker (e.g., Node-RED) for visualization and monitoring.
# System Architecture
## 1. Sensors:
DHT22: Measures temperature and humidity.
PIR: Detects motion.
LDR: Measures ambient light levels to control lighting.
## 2. Actuators:
LEDs: Turns on/off based on motion and light levels.
Buzzer: Activated as an alarm upon detecting motion.
## 3. Communication:
ESP32: Handles sensor readings, actuator control, and communication with MQTT broker and Blynk.
MQTT: Data is sent to an MQTT broker (e.g., Node-RED) for visualization and monitoring.
Blynk: Provides a mobile interface to control LEDs and buzzer remotely.
# Software Requirements:
Wokwi: For simulating the ESP32 and sensors.
Blynk App: To control LEDs and buzzer remotely.
Node-RED: For visualization of sensor data and actuator status.
MQTT Broker: HiveMQ.
# Setup Instructions
## 1. Setup Blynk
### 1.1 Install the Blynk App
Download and install the Blynk app from the Google Play Store or Apple App Store.
### 1.2 Create a Blynk Account
Open the Blynk app.
Sign up for a new account if you don't already have one, or log in if you have an existing account.
### 1.3 Create a New Project in Blynk
Open the Blynk app and tap on Create New Project.
Enter a name for your project (e.g., "Smart Home").
Select the device as ESP32.
Tap Create to generate the project.
After creation, Blynk will show you an Auth Token. This is an important token that will be used to connect your ESP32 to the Blynk cloud. Copy this token and keep it in a safe place.
### 1.4 Add Virtual Pins for Control
In the Blynk app, add the following virtual pins to control devices:
V5: For controlling LED1.
V6: For controlling LED2.
V7: For controlling the Buzzer.
Add appropriate widgets for each virtual pin:
For LED1 and LED2, use a Button widget or Switch widget to turn the LEDs on and off.
For Buzzer, use a Button or Switch widget to control the buzzer.
For each widget, configure it to use the corresponding virtual pin (V5, V6, V7) and set the widget’s behavior to either Push or Switch.
## 2. Setup Node-RED Flow
Node-RED is used as the cloud platform for your Smart Home System. It processes the combined sensor data sent by the ESP32 and visualizes it on a dashboard with widgets for temperature, humidity, light, motion, buzzer, and LED status.

### 2.1 Input Node:
MQTT-IN Node: Subscribe to the Topic
The MQTT-IN node subscribes to the sensors/data topic, which receives a JSON payload from the ESP32 containing all the sensor data.
Drag an MQTT-IN node to the flow.
Configure the MQTT-IN node:
Set the Server to your MQTT broker (e.g., localhost or broker URL).
Set the Topic to sensors/data, which is the topic your ESP32 will publish data to.
Set the QoS to 0 for the lowest delivery guarantee.
Name the node (e.g., "Subscribe to sensor data").
Example JSON payload:

json
Copy code
{
  "temperature": 22.5,
  "humidity": 60,
  "light": 75,
  "motion": "no_motion",
  "buzzer": "OFF",
  "leds": "ON"
}
This JSON payload is sent to the next node for further processing.

### 2.2 Change Node:
Extract Individual Sensor Data
The Change node is used to extract individual sensor data from the JSON payload received by the MQTT-IN node.
Drag a Change node and link it to the MQTT-IN node.
Configure the Change Node to extract specific data for each sensor:
For Temperature: Set msg.payload.temperature.
For Humidity: Set msg.payload.humidity.
For Light Intensity: Set msg.payload.light.
For Motion: Set msg.payload.motion.
For Buzzer: Set msg.payload.buzzer.
For LEDs: Set msg.payload.leds.
Each extracted data item is now available for use in your dashboard widgets (gauge, text, etc.).
### 2.3 Dashboard Nodes:
Display Data in Dashboard Widgets
The extracted data from the Change node is sent to different dashboard nodes for visualization.

Temperature Gauge (ui-gauge node):

Displays the current temperature.
Set msg.payload to msg.payload.temperature from the Change node.
Humidity Gauge (ui-gauge node):

Displays the current humidity.
Set msg.payload to msg.payload.humidity.
Light Intensity Gauge (ui-gauge node):

Displays the light intensity level.
Set msg.payload to msg.payload.light.
Motion Status (ui-text node):

Displays whether motion is detected or not.
Set msg.payload to msg.payload.motion.
Buzzer Status (ui-text node):

Displays whether the buzzer is ON or OFF.
Set msg.payload to msg.payload.buzzer.
LED Status (ui-text node):

Displays whether the LEDs are ON or OFF.
Set msg.payload to msg.payload.leds.
