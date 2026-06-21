import paho.mqtt.client as mqtt
import json
import csv
import os
import time
import datetime
import psutil
import subprocess

# --- CONFIGURARE ---
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 8883
MQTT_TOPIC = "home/sensors/sensor-1"
CSV_FILE = "dataset_final_ai.csv"
CA_CERT = "/etc/mosquitto/certs/ca.crt"

def get_rpi_metrics():
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
        out = subprocess.check_output(['ping', '-c', '1', '-W', '1', '8.8.8.8'], stderr=subprocess.STDOUT, universal_ne>)
        if "time=" in out:
            idx = out.find("time=")
            latency = float(out[idx+5:out.find(" ms", idx)])
    except: pass

    return temp, cpu, ram, disk, uptime, rssi, latency, proc_cnt

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        esp_data = json.loads(msg.payload.decode())
        r_temp, r_cpu, r_ram, r_disk, r_upt, r_rssi, r_lat, r_proc = get_rpi_metrics()

        full_row = esp_data.copy()

        full_row['timestamp_local'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_row['rpi_temp'] = r_temp
        full_row['rpi_cpu'] = r_cpu
        full_row['rpi_ram'] = r_ram
        full_row['rpi_disk'] = r_disk
        full_row['rpi_uptime'] = int(r_upt)
        full_row['rpi_rssi'] = r_rssi
        full_row['rpi_net_lat'] = r_lat
        full_row['rpi_proc_cnt'] = r_proc

        file_exists = os.path.isfile(CSV_FILE)

        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=full_row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(full_row)

        print(f"SAVED | ESP Heap: {esp_data.get('esp_heap')} | RPi CPU: {r_cpu}% | Latency: {r_lat}ms")

    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # AICI AM FACUT MODIFICAREA PENTRU VERSIUNEA NOUA:
    # Îi spunem explicit să folosească VERSION1 pentru a fi compatibil cu callback-urile vechi
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "DataCollector_AI")

    client.tls_set(ca_certs=CA_CERT)
    client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, 60) 
    client.loop_forever()