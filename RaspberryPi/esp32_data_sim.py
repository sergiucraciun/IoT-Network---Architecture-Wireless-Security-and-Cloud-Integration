import paho.mqtt.client as mqtt
from datetime import datetime
import ssl
import time
import random
import json

# MQTT config
BROKER = "192.168.10.220"
PORT = 8883
TOPIC_TEMPLATE = "home/sensors/sensor-{}" # sensor-1, sensor-2
CA_CERT = "E:\IT\IoT-Architecture\RaspberryPi\ca.crt"

# Create MQTT client
client = mqtt.Client()

# TLS Configuration
client.tls_set(
    ca_certs=CA_CERT,
    certfile=None,
    keyfile=None,
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLSv1_2
)

client.tls_insecure_set(True) # Accept self-signed or CN mismatch

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")

client.on_connect = on_connect

# Connect to broker
client.connect(BROKER, PORT)
client.loop_start()

try:
    while True:
        for sensor_id in [1, 2]:
            # Generate random temperature and humidity
            temperature = round(random.uniform(24.0, 25.0), 1)
            humidity = round(random.uniform(40.0, 60.0), 1)

            # Create JSON payload
            payload = {
                "sensor_id": f"sensor-{sensor_id}",
                "timestamp": datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S"),
                "temperature": temperature,
                "humidity": humidity
            }

            topic = TOPIC_TEMPLATE.format(sensor_id)
            message = json.dumps(payload)

            client.publish(topic, message)
            print(f"Published to {topic}: {message}")

        time.sleep(2) # wait before sending next

except KeyboardInterrupt:
    print("Exiting...")
    client.loop_stop()
    client.disconnect()