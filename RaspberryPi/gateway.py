#varianta functionala pana la imeplementarea /offline


import paho.mqtt.client as mqtt
from datetime import datetime, timezone
import hashlib
import hmac
import base64
import urllib.parse
import json
import requests
import uuid
import time
import threading
import statistics 
import psutil     
import subprocess 
import os

# ----------------------------------------------------
# 1. CONFIGURARE AZURE & RPi GATEWAY ID
# ----------------------------------------------------

AZURE_API_BASE = "https://iot-backend-app-ger.kindbay-166d1581.germanywestcentral.azurecontainerapps.io"
GATEWAY_ID = "rpi-gateway-1"
POLLING_INTERVAL = 5

# Configurarea Cosmos DB
COSMOS_DB_URI = "https://iotprojectdb1.documents.azure.com:443/"
COSMOS_DB_KEY = "3v3HRzxc3BpExkO6ZzlJeJ7WraI5qtZKjZJO3vguct0d5Jcugp"
COSMOS_DB_DB = "iot_database"
COSMOS_DB_CONTAINER = "sensor_data"

# Memoria globala pentru calcule matematice (Delta & Rolling Window)
sensor_history = {}

# ----------------------------------------------------
# 2. FUNCTII DE BAZA 
# ----------------------------------------------------

# Citirea metricilor Raspberry Pi
def get_rpi_metrics():
    """Funcția ta originală pentru a citi starea Raspberry Pi"""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
    except: temp = 0.0

    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    uptime = time.time() - psutil.boot_time()
    proc_cnt = len(psutil.pids())

    rssi = -100
    try:
        with open('/proc/net/wireless', 'r') as f:
            for line in f:
                if "wlan0" in line:
                    rssi = float(line.split()[3].replace('.', ''))
    except: pass

    latency = 999.0
    try:
        # Ping Google DNS for connectivity check
        out = subprocess.check_output(['ping', '-c', '1', '-W', '1', '8.8.8.8'], stderr=subprocess.STDOUT, universal_newlines=True)
        if "time=" in out:
            idx = out.find("time=")
            latency = float(out[idx+5:out.find(" ms", idx)])
    except: pass

    return temp, cpu, ram, disk, uptime, rssi, latency, proc_cnt


# Build Cosmos DB authorization headers (Rămâne neschimbată)
def build_auth_headers(verb, resource_type, resource_link):
    utc_now = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    text = (verb.lower() + "\n" + resource_type.lower() + "\n" + resource_link + "\n" + utc_now.lower() + "\n" + "" + "\n")
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


# Send data to Cosmos DB (Rămâne neschimbată)
def send_to_cosmos(data):
    resource_link = f"dbs/{COSMOS_DB_DB}/colls/{COSMOS_DB_CONTAINER}"
    headers = build_auth_headers("POST", "docs", resource_link)
    headers["x-ms-documentdb-partitionkey"] = json.dumps([data["sensor_id"]])
    url = f"{COSMOS_DB_URI}dbs/{COSMOS_DB_DB}/colls/{COSMOS_DB_CONTAINER}/docs"
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"Cosmos DB response (Forwarder): {response.status_code}")


# MQTT callbacks (Rămân neschimbate)
def on_connect(client, userdata, flags, rc):
    print("Connected to local broker with result code", rc)
    client.subscribe("home/sensors/#")


def on_message(client, userdata, msg):
    global sensor_history
    print(f"Received: {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())
        payload["gateway_id"] = GATEWAY_ID
        sensor_id = msg.topic

        # Extragem datele curente necesare pentru calcule (folosim 0 ca default)
        curr_temp = float(payload.get("temperature", 0))
        curr_hum  = float(payload.get("humidity", 0))
        curr_heap = float(payload.get("esp_heap", 0))
        curr_rssi = float(payload.get("esp_rssi", -60))

        temp_delta = 0.0
        hum_delta  = 0.0
        heap_delta = 0.0
        rssi_var = 0.0

        if sensor_id in sensor_history:
            history = sensor_history[sensor_id]
            
            # Calculăm diferența față de ultima valoare (Viteza de schimbare)
            temp_delta = curr_temp - history["last_temp"]
            hum_delta  = curr_hum  - history["last_hum"]
            heap_delta = curr_heap - history["last_heap"]
            
            # Gestionăm lista de RSSI pentru a calcula varianța (fereastră de 10)
            history["rssi_list"].append(curr_rssi)
            if len(history["rssi_list"]) > 10:
                history["rssi_list"].pop(0)
            
            # Calculăm deviația standard (dacă avem destule date)
            if len(history["rssi_list"]) > 1:
                rssi_var = statistics.stdev(history["rssi_list"])
            
            # Actualizăm istoricul cu valorile curente
            history["last_temp"] = curr_temp
            history["last_heap"] = curr_heap
            
        else:
            # Prima dată când vedem senzorul: inițializăm istoricul
            sensor_history[sensor_id] = {
                "last_temp": curr_temp,
                "last_hum":  curr_hum,
                "last_heap": curr_heap,
                "rssi_list": [curr_rssi]
            }
        
        r_temp, r_cpu, r_ram, r_disk, r_upt, r_rssi, r_lat, r_proc = get_rpi_metrics()

        # Variabilele calculate (AI Features)
        payload["temp_delta"] = round(temp_delta, 1)
        payload["hum_delta"]  = round(hum_delta, 1)
        payload["heap_delta"] = int(heap_delta)
        payload["rssi_var"] = round(rssi_var, 1)

        # Variabilele Raspberry
        payload["rpi_temp"]     = round(r_temp, 1)
        payload["rpi_cpu"]      = round(r_cpu, 1)
        payload["rpi_ram"]      = round(r_ram, 1)
        payload["rpi_disk"]     = round(r_disk, 1)
        payload["rpi_uptime"]   = int(r_upt)
        payload["rpi_rssi"]     = round(r_rssi, 1)
        payload["rpi_net_lat"]  = round(r_lat, 1)
        payload["rpi_proc_cnt"] = int(r_proc)

        # Metadate suplimentare
        payload["sensor_id"] = msg.topic
        payload["id"] = str(uuid.uuid4())
        
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Rotunjiri standard
        if "temperature" in payload:
            payload["temperature"] = round(float(payload["temperature"]), 1)
        if "humidity" in payload:
            payload["humidity"] = round(float(payload["humidity"]), 1)

        send_to_cosmos(payload)

    except Exception as e:
        print(f"Failed to forward data to Cosmos DB: {e}")

# ----------------------------------------------------
# 3. LOGICA REVERSE POLLING (PRIMIRE COMANDA)
# ----------------------------------------------------

def execute_and_acknowledge(command):
    """
    Execută comanda primită din Cloud și trimite confirmarea.
    """
    command_id = command.get("id")
    action_type = command.get("action")
    target_sensor_id = command.get("sensor_id")

    print(f"EXECUTING: {action_type} for sensor {target_sensor_id}")

    # --- 1. Logica de Execuție Locală (MQTT Push) ---
    # Publică comanda pe topicul MQTT local, unde ESP-ul ascultă.
    try:
        # Preluăm doar ID-ul senzorului (Ex: sensor-1)
        local_mqtt_topic = f"home/commands/{target_sensor_id.split('/')[-1]}"
        client.publish(local_mqtt_topic, json.dumps(command))
        print(f"Forwarded command to local MQTT topic: {local_mqtt_topic}")
    except Exception as e:
        print(f"Failed to forward command via MQTT: {e}")
        return

    # --- 2. Trimite Acknowledge (PATCH) către Azure ---
    # Marchează comanda ca executată în Cosmos DB.
    try:
        url_acknowledge = f"{AZURE_API_BASE}/command/acknowledge/{command_id}"

        # Nu avem nevoie de antete complexe; PATCH-ul trimite un corp gol.
        ack_response = requests.patch(url_acknowledge, json={"executed": True})

        if ack_response.status_code == 200:
            print(f"ACK Success: Command {command_id} marked as EXECUTED.")
        else:
            print(f"ACK Failed: Azure returned {ack_response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"Network error during ACK: {e}")


def check_command_queue():
    """
    Pollează Azure Backend pentru a verifica dacă există comenzi noi.
    """
    url_polling = f"{AZURE_API_BASE}/command-queue/{GATEWAY_ID}"

    try:
        # RPi-ul inițiază cererea GET
        response = requests.get(url_polling)

        # Verifica 200 OK
        if response.status_code == 200:
            command_response = response.json()

            # Verifică statusul: sunt comenzi de executat sau răspuns No Content?
            if command_response.get("status") == "No pending commands":
                # Nu există comenzi noi
                return
            else:
                # Comandă(listă de comenzi) găsită!
                # NOTA: Chiar dacă ai cerut TOP 1, tratează răspunsul ca pe o listă pentr>
                if isinstance(command_response, dict) and command_response.get('id'):
                    execute_and_acknowledge(command_response)

        else:
            print(f"Error polling Azure: Status {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"Network error during polling: {e}")


# ----------------------------------------------------
# 4. PUNCTUL DE INTRARE (RULEAZĂ AMBELE SERVICII)
# ----------------------------------------------------


def polling_loop():
    """Rulează bucla de Reverse Polling la intervale fixe."""
    while True:
        check_command_queue()
        time.sleep(POLLING_INTERVAL) # Așteaptă 5 secunde

if __name__ == '__main__':
    # Pornirea MQTT (rămâne necesară pentru on_message)
    client = mqtt.Client()
    client.tls_set(ca_certs="/etc/mosquitto/certs/ca.crt")
    client.tls_insecure_set(True)
    client.on_connect = on_connect
    client.on_message = on_message

    # ATENȚIE: Asigură-te că IP-ul brokerului tău local (Mosquitto) este corect
    client.connect("192.168.10.220", 8883)

    # Lansează funcția de Polling într-un thread separat
    polling_thread = threading.Thread(target=polling_loop, daemon=True)
    polling_thread.start()

    # Rămâne bucla principală MQTT (pentru a primi mesaje de la ESP)
    client.loop_forever()