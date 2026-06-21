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
import sqlite3
import statistics
import psutil
import subprocess
import os

# ----------------------------------------------------
# 1. CONFIGURARE
# ----------------------------------------------------

AZURE_API_BASE = "https://iot-backend-app-ger.kindbay-166d1581.germanywestcentral.azurecontainerapps.io"
GATEWAY_ID = "rpi-gateway-1"
POLLING_INTERVAL = 5

# Cosmos DB Config
COSMOS_DB_URI = "https://iotprojectdb1.documents.azure.com:443/"
COSMOS_DB_KEY = "3v3HRzxc3BpExkO6ZzlJeJ7WraI5qtZKjZJO3vguct0d5Jcu"
COSMOS_DB_DB = "iot_database"

# Containere (Tabele Cloud)
CONTAINER_LIVE = "sensor_data"       # Hot Path (Date Live)
CONTAINER_ARCHIVE = "offline_archive" # Cold Path (Istoric/Recuperat)

# Buffer Local (Disc)
SQLITE_DB_FILE = "gateway_buffer.db"

# --- LOCK GLOBAL PENTRU SQLITE ---
# Acesta previne eroarea "Database is locked" când două procese încearcă să scrie simultan
sqlite_lock = threading.Lock()

# Memorie globală pentru calcule matematice (Delta)
sensor_history = {}

# ----------------------------------------------------
# 2. SQLITE BUFFER (SALVARE LOCALĂ)
# ----------------------------------------------------

def init_sqlite():
    """Creează baza de date locală dacă nu există."""
    try:
        # Folosim Lock-ul pentru a fi siguri că nimeni altcineva nu umblă la fișier
        with sqlite_lock:
            conn = sqlite3.connect(SQLITE_DB_FILE)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS buffer
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          target_container TEXT, 
                          payload TEXT)''')
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"❌ SQLite Init Error: {e}")

def save_to_sqlite(target_container, payload):
    """Salvează datele pe disc când RPi nu are internet."""
    try:
        with sqlite_lock:
            conn = sqlite3.connect(SQLITE_DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO buffer (target_container, payload) VALUES (?, ?)", 
                      (target_container, json.dumps(payload)))
            conn.commit()
            conn.close()
        print(f"💾 [RPi OFFLINE] Data buffered locally.")
    except Exception as e:
        print(f"❌ SQLite Write Error: {e}")

# ----------------------------------------------------
# 3. METRICI & CLOUD
# ----------------------------------------------------

def get_rpi_metrics():
    """Citește starea Raspberry Pi (Full Stats)."""
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
        # Ping Google DNS rapid
        out = subprocess.check_output(['ping', '-c', '1', '-W', '1', '8.8.8.8'], stderr=subprocess.STDOUT, universal_newlines=True)
        if "time=" in out:
            idx = out.find("time=")
            latency = float(out[idx+5:out.find(" ms", idx)])
    except: pass

    return temp, cpu, ram, disk, uptime, rssi, latency, proc_cnt

def build_auth_headers(verb, resource_type, resource_link):
    utc_now = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
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

def send_to_cosmos(payload, target_container):
    """
    Trimite la Azure.
    Succes -> Returnează True.
    Eșec (Fără Net) -> Salvează în SQLite și Returnează False.
    """
    resource_link = f"dbs/{COSMOS_DB_DB}/colls/{target_container}"
    headers = build_auth_headers("POST", "docs", resource_link)
    
    # Partition Key (RĂMAS NEMODIFICAT, exact cum ai cerut)
    p_key = payload.get("sensor_id", "unknown")
    headers["x-ms-documentdb-partitionkey"] = json.dumps([p_key])
    
    url = f"{COSMOS_DB_URI}dbs/{COSMOS_DB_DB}/colls/{target_container}/docs"
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=3)
        
        if response.status_code in [200, 201]:
            container_tag = "[LIVE]" if target_container == CONTAINER_LIVE else "[ARCHIVE]"
            print(f"☁️ {container_tag} Sent to Azure: {response.status_code}")
            return True
        else:
            print(f"⚠️ Azure API Error {response.status_code}: {response.text}")
            raise Exception("Azure Rejected")

    except Exception as e:
        print(f"⚠️ Cloud unreachable ({e}). Buffering...")
        
        # Dacă ajungem aici, RPi este Offline
        payload["rpi_offline"] = True
        
        # Orice dată care a stat în buffer, devine automat "Arhivă"
        save_to_sqlite(CONTAINER_ARCHIVE, payload)
        return False

# ----------------------------------------------------
# 4. SYNC THREAD (RECOVERY)
# ----------------------------------------------------
def sqlite_sync_loop():
    """Golește bufferul local când revine internetul."""
    while True:
        try:
            # --- FIX: Lock la citire ---
            rows = []
            with sqlite_lock:
                conn = sqlite3.connect(SQLITE_DB_FILE)
                c = conn.cursor()
                # Luăm cele mai vechi 10 mesaje
                c.execute("SELECT id, target_container, payload FROM buffer ORDER BY id ASC LIMIT 10")
                rows = c.fetchall()
                conn.close()
            
            if not rows:
                time.sleep(5) 
                continue

            print(f"🔄 Syncing {len(rows)} records from Buffer to Cloud...")
            
            for row in rows:
                row_id = row[0]
                target = row[1] # De obicei va fi CONTAINER_ARCHIVE
                payload = json.loads(row[2])
                
                # Reconstruim logica de request pură pentru sync
                resource_link = f"dbs/{COSMOS_DB_DB}/colls/{target}"
                headers = build_auth_headers("POST", "docs", resource_link)
                
                # Păstrăm Partition Key exact cum vrei tu (fără split)
                p_key = payload.get("sensor_id", "unknown")
                headers["x-ms-documentdb-partitionkey"] = json.dumps([p_key])
                
                url = f"{COSMOS_DB_URI}dbs/{COSMOS_DB_DB}/colls/{target}/docs"

                try:
                    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=3)
                    if resp.status_code in [200, 201]:
                        # --- FIX: Lock la ștergere ---
                        with sqlite_lock:
                            conn = sqlite3.connect(SQLITE_DB_FILE)
                            c = conn.cursor()
                            c.execute("DELETE FROM buffer WHERE id=?", (row_id,))
                            conn.commit()
                            conn.close()
                        print(f"   -> Synced ID {row_id}")
                    else:
                        break # Stop dacă Azure dă eroare
                except:
                    break # Stop dacă nu e net
            
            time.sleep(2)

        except Exception as e:
            print(f"Sync Thread Error: {e}")
            time.sleep(5)

# ----------------------------------------------------
# 5. MQTT LOGIC (MAIN)
# ----------------------------------------------------

def on_connect(client, userdata, flags, rc):
    print("Connected to Mosquitto. Subscribing...")
    client.subscribe("home/sensors/#")
    client.subscribe("home/offline/#")

def on_message(client, userdata, msg):
    global sensor_history
    topic = msg.topic
    
    try:
        payload = json.loads(msg.payload.decode())
        current_time_iso = datetime.now(timezone.utc).isoformat()
        
        # ID-uri Standard
        payload["gateway_id"] = GATEWAY_ID
        payload["id"] = str(uuid.uuid4())
        
        # --- CAZUL 1: DATE LIVE (ESP Online) ---
        if "sensors" in topic:
            payload["timestamp"] = current_time_iso
            payload["sensor_id"] = topic
            
            # Flags Stare
            payload["esp_offline"] = False
            payload["rpi_offline"] = False 

            # Calcule Delta
            curr_temp = float(payload.get("temperature", 0))
            curr_hum  = float(payload.get("humidity", 0))
            curr_heap = float(payload.get("esp_heap", 0))
            curr_rssi = float(payload.get("esp_rssi", -60))

            temp_delta, hum_delta, heap_delta, rssi_var = 0.0, 0.0, 0.0, 0.0

            if topic in sensor_history:
                history = sensor_history[topic]
                temp_delta = curr_temp - history["last_temp"]
                hum_delta  = curr_hum  - history["last_hum"]
                heap_delta = curr_heap - history["last_heap"]
                
                history["rssi_list"].append(curr_rssi)
                if len(history["rssi_list"]) > 10: history["rssi_list"].pop(0)
                
                # --- FIX: Protecție stdev ---
                if len(history["rssi_list"]) > 1:
                    try:
                        rssi_var = statistics.stdev(history["rssi_list"])
                    except:
                        rssi_var = 0.0
                
                history["last_temp"] = curr_temp
                history["last_heap"] = curr_heap
            else:
                sensor_history[topic] = {
                    "last_temp": curr_temp, "last_hum": curr_hum,
                    "last_heap": curr_heap, "rssi_list": [curr_rssi]
                }

            # Metrici RPi COMPLETE
            r_temp, r_cpu, r_ram, r_disk, r_upt, r_rssi, r_lat, r_proc = get_rpi_metrics()
            
            payload["temp_delta"] = round(temp_delta, 1)
            payload["hum_delta"]  = round(hum_delta, 1)
            payload["heap_delta"] = int(heap_delta)
            payload["rssi_var"]   = round(rssi_var, 1)
            
            payload["rpi_temp"]     = round(r_temp, 1)
            payload["rpi_cpu"]      = round(r_cpu, 1)
            payload["rpi_ram"]      = round(r_ram, 1)
            payload["rpi_disk"]     = round(r_disk, 1)
            payload["rpi_uptime"]   = int(r_upt)
            payload["rpi_rssi"]     = round(r_rssi, 1)
            payload["rpi_net_lat"]  = round(r_lat, 1)
            payload["rpi_proc_cnt"] = int(r_proc)
            
            # Rotunjiri
            if "temperature" in payload: payload["temperature"] = round(float(payload["temperature"]), 1)
            if "humidity" in payload: payload["humidity"] = round(float(payload["humidity"]), 1)

            # Trimite la LIVE
            send_to_cosmos(payload, CONTAINER_LIVE)

        # --- CAZUL 2: DATE OFFLINE (ESP a fost Offline) ---
        elif "offline" in topic:
            real_sensor_topic = topic.replace("offline", "sensors")
            
            clean_payload = {
                "gateway_id": GATEWAY_ID,
                "sensor_id": real_sensor_topic,
                "id": str(uuid.uuid4()),
                "timestamp": current_time_iso,
                "relative_timestamp": payload.get("esp_uptime"),
                
                # Flags Stare
                "esp_offline": True,
                "rpi_offline": False, # Se schimba daca nu e net
                
                # Date brute
                "temperature": round(float(payload.get("temperature", 0)), 1),
                "humidity": round(float(payload.get("humidity", 0)), 1),
                
                # Metadata
                "esp_id": payload.get("esp_id"),
                "esp_ip": payload.get("esp_ip"),
                "esp_boot": payload.get("esp_boot"),
                "session_id": payload.get("session_id"),
                "esp_msg_c": payload.get("esp_msg_c")
            }

            # Trimite la ARHIVA
            send_to_cosmos(clean_payload, CONTAINER_ARCHIVE)

    except Exception as e:
        print(f"Msg Processing Error: {e}")

# ----------------------------------------------------
# 6. COMMANDS (POLLING)
# ----------------------------------------------------

def execute_and_acknowledge(command):
    command_id = command.get("id")
    action_type = command.get("action")
    target_sensor_id = command.get("sensor_id")
    print(f"EXECUTING: {action_type} for {target_sensor_id}")

    try:
        local_mqtt_topic = f"home/commands/{target_sensor_id.split('/')[-1]}"
        client.publish(local_mqtt_topic, json.dumps(command))
    except Exception as e:
        print(f"MQTT Cmd Error: {e}")
        return

    try:
        url_ack = f"{AZURE_API_BASE}/command/acknowledge/{command_id}"
        requests.patch(url_ack, json={"executed": True})
        print(f"ACK Sent for {command_id}")
    except Exception as e:
        print(f"ACK Error: {e}")

def check_command_queue():
    try:
        url = f"{AZURE_API_BASE}/command-queue/{GATEWAY_ID}"
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") != "No pending commands":
                if isinstance(data, dict) and data.get('id'):
                    execute_and_acknowledge(data)
    except Exception as e:
        print(f"Polling Error: {e}")

def polling_loop():
    while True:
        check_command_queue()
        time.sleep(POLLING_INTERVAL)

# ----------------------------------------------------
# 7. START
# ----------------------------------------------------
if __name__ == '__main__':
    init_sqlite()

    client = mqtt.Client()
    client.tls_set(ca_certs="/etc/mosquitto/certs/ca.crt")
    client.tls_insecure_set(True)
    client.on_connect = on_connect
    client.on_message = on_message

    # Conectare la Broker Local
    client.connect("192.168.10.220", 8883)

    # Thread 1: Comenzi
    threading.Thread(target=polling_loop, daemon=True).start()

    # Thread 2: Sync Offline
    threading.Thread(target=sqlite_sync_loop, daemon=True).start()

    client.loop_forever()