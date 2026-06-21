import paho.mqtt.client as mqtt
import datetime
import hashlib
import hmac
import base64
import urllib.parse
import json
import requests
import uuid

# Cosmos DB configuration
COSMOS_DB_URI = "https://iotprojectdb1.documents.azure.com:443/"
COSMOS_DB_KEY = "3v3HRzxc3BpExkO6ZzlJeJ7WraI5qtZKjZJO3vguct0d5Jcu"
COSMOS_DB_DB = "iot_database"
COSMOS_DB_CONTAINER = "sensor_data"

# Build Cosmos DB authorization headers
def build_auth_headers(verb, resource_type, resource_link):
    utc_now = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    text = (verb.lower() + "\n" +
            resource_type.lower() + "\n" +
            resource_link + "\n" +
            utc_now.lower() + "\n" +
            "" + "\n")

    key = base64.b64decode(COSMOS_DB_KEY)
    sig = base64.b64encode(hmac.new(key, text.encode("utf-8"), hashlib.sha256).digest()).decode()

    auth_str = f"type=master&ver=1.0&sig={sig}"
    auth_encoded = urllib.parse.quote(auth_str)

    return {
        "Authorization": auth_encoded,
        "x-ms-date": utc_now,
        "x-ms-version": "2018-12-31",
        "Content-Type": "application/json"
    }

# Send data to Cosmos DB
def send_to_cosmos(data):
    resource_link = f"dbs/{COSMOS_DB_DB}/colls/{COSMOS_DB_CONTAINER}"
    headers = build_auth_headers("POST", "docs", resource_link)

    # Set partition key based on topic
    headers["x-ms-documentdb-partitionkey"] = json.dumps([data["sensor_id"]])

    url = f"{COSMOS_DB_URI}dbs/{COSMOS_DB_DB}/colls/{COSMOS_DB_CONTAINER}/docs"

    response = requests.post(url, headers=headers, data=json.dumps(data))
    print("Cosmos DB response:", response.status_code, response.text)

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe("home/sensors/#")

def on_message(client, userdata, msg):
    print(f"Received: {msg.topic} {msg.payload.decode()}")
    try:
        raw_payload = json.loads(msg.payload.decode())
        formatted_data = {
            "id": str(uuid.uuid4()),
            "sensor_id": msg.topic,
            # Generăm timestamp-ul cu spațiu, exact cum era cel vechi
            "timestamp": datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "temperature": raw_payload.get("temp"),
            "humidity": raw_payload.get("hum")
        }

        send_to_cosmos(formatted_data)
    except Exception as e:
        print("Failed to send to Cosmos DB:", e)

# MQTT client setup
client = mqtt.Client()
client.tls_set(ca_certs="/etc/mosquitto/certs/ca.crt")
client.tls_insecure_set(True)
client.on_connect = on_connect
client.on_message = on_message

client.connect("192.168.20.1", 8883)  # Replace with your broker IP if different
client.loop_forever()