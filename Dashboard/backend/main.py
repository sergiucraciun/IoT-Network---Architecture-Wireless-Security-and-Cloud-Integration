import os
import uuid
from datetime import datetime, timezone
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from azure.cosmos import CosmosClient
from ai_service import start_ai_loop, init_db_containers


# ==========================================
# 1. CONFIGURARE & CONEXIUNE AZURE
# ==========================================

timestamp = datetime.now(timezone.utc).isoformat()

app = FastAPI()

# Configurare CORS (Permite frontend-ului să vorbească cu backend-ul)
origins = ["*"] # În producție, pune doar domeniul tău specific
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Datele de conectare la Cosmos DB
COSMOS_DB_URI = os.getenv("COSMOS_DB_URI", "https://iotprojectdb1.documents.azure.com:443/")
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY", "3v3HRzxc3BpExkO6ZzlJeJ7WraI5qtZKjZJO3vguct0d5JcugpbYhplapSXrShHIU6j8rHje45R4ACDbYmK0wQ==")
COSMOS_DB_DB_NAME = "iot_database"


# Inițializare Client Azure
try:
    client = CosmosClient(COSMOS_DB_URI, credential=COSMOS_DB_KEY)
    database = client.get_database_client(COSMOS_DB_DB_NAME)
    
    # Conectare la containere (tabele)
    container_telemetry = database.get_container_client("sensor_data")
    container_commands = database.get_container_client("commands")
    container_rules = database.get_container_client("automation_rules")
    container_devices = database.get_container_client("devices") 

    # Verificam daca exista containerul de alerte
    try:
        container_alerts = database.get_container_client("alerts")
    except:
        container_alerts = None
        print("Alerts container missing")
    
    print(" Conectat la Azure Cosmos DB cu succes!")
except Exception as e:
    print(f" Eroare critică la conectarea Cosmos DB: {e}")


# ==========================================
# 2. ENDPOINTS: DEVICE REGISTRY 
# ==========================================

@app.get("/devices")
def get_all_devices():
    """Returnează lista tuturor senzorilor înregistrați."""
    try:
        query = "SELECT * FROM c"
        items = list(container_devices.query_items(query=query, enable_cross_partition_query=True))
        return {"devices": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#Endpoint Unificat: Creează Senzori SAU Gateway-uri.
@app.post("/devices")
def register_device(device_data: dict):

    try:
        # 1. Validăm datele primite din Frontend
        if "id" not in device_data or "friendly_name" not in device_data or "type" not in device_data:
            raise HTTPException(status_code=400, detail="Missing required fields (id, friendly_name, type)")
        
        device_type = device_data["type"] # 'sensor' sau 'gateway'
        device_id = device_data["id"]

        # 2. Construim obiectul STANDARD (Backend-ul face legea)
        new_device = {
            "id": device_id,
            "friendly_name": device_data["friendly_name"],
            "location": device_data.get("location", "Unassigned"),
            "type": device_type,
            
            # --- CÂMPURILE AUTOMATE (STANDARD) ---
            "status": "OFFLINE",
            "timestamp_last_seen": None 
        }

        # 3. Logică specifică pentru Senzori
        if device_type == "sensor":
            new_device["telemetry_topic"] = f"home/sensors/{device_id}"
            new_device["command_topic"] = f"home/commands/{device_id}"

        # 4. Salvare în bază (Upsert = Repară dacă există deja, Creează dacă nu)
        container_devices.upsert_item(body=new_device)

        return {"status": "Device Registered", "device": new_device}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/devices/{device_id}")
def delete_device(device_id: str):
    """Șterge un senzor."""
    try:
        container_devices.delete_item(item=device_id, partition_key=device_id)
        return {"status": "Device Deleted"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==========================================
# 3. ENDPOINTS: TELEMETRY & COMMANDS
# ==========================================

@app.get("/last-readings")
def get_last_readings(sensor_id: str, limit: int = 20):
    """Returnează istoricul pentru grafice."""
    try:
        query = f"SELECT TOP {limit} * FROM c WHERE c.sensor_id = '{sensor_id}' ORDER BY c._ts DESC"
        items = list(container_telemetry.query_items(query=query, enable_cross_partition_query=True))
        return items
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

@app.post("/command")
def send_command(command: dict):
    """Primește o comandă manuală de la Frontend."""
    if "action" not in command or "sensor_id" not in command:
        raise HTTPException(status_code=400, detail="Missing data")
    
    command_doc = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "gateway_id": "rpi-gateway-1", # Hardcodat pt acest proiect
        "sensor_id": command.get("sensor_id"),
        "command_status": "PENDING", 
        "action": command.get("action"),
        "executed": False,
        "source": "MANUAL_DASHBOARD"
    }
    
    try:
        container_commands.upsert_item(body=command_doc)
        return {"status": "Command accepted", "id": command_doc["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint pentru RPi Gateway (Heartbeat & Commands)
@app.get("/command-queue/{gateway_id}")
def get_pending_command(gateway_id: str):

    try:
        current_ts = datetime.now(timezone.utc).isoformat()
        
        try:
            # 1. Căutăm dispozitivul
            device_item = container_devices.read_item(item=gateway_id, partition_key=gateway_id)

            # --- LOGICA HEARTBEAT (Update Last Seen) ---
            last_ts_str = device_item.get('timestamp_last_seen')
            should_update = True
            
            if last_ts_str:
                try:
                    last_ts = datetime.fromisoformat(last_ts_str)
                    if last_ts.tzinfo is None:
                        last_ts = last_ts.replace(tzinfo=timezone.utc)
                    
                    diff = (datetime.now(timezone.utc) - last_ts).total_seconds()
                    
                    # Optimizare: Scriem în DB doar la fiecare 5 secunde
                    if diff < 5: 
                        should_update = False
                except:
                    should_update = True 
            
            if should_update:
                device_item['timestamp_last_seen'] = current_ts
                device_item['status'] = 'ONLINE' 
                
                container_devices.upsert_item(device_item)

        except Exception:
            print(f"⛔ SECURITY: Unauthorized Gateway tried to connect: {gateway_id}")
            return {"status": "Unauthorized Device"}
            
    except Exception as e:
        print(f"Heartbeat error: {e}")

    # Returnează comenzile
    try:
        query = f"SELECT TOP 1 * FROM c WHERE c.gateway_id = '{gateway_id}' AND c.executed = false ORDER BY c.timestamp DESC"
        items = list(container_commands.query_items(query=query, enable_cross_partition_query=True))
        if not items: return {"status": "No commands"}
        return items[0]
    except:
        return {"status": "No commands"}


@app.patch("/command/acknowledge/{command_id}")
def acknowledge_command(command_id: str):
    # Aici RPi confirmă că a executat comanda
    try:
        # Citim item-ul
        item = container_commands.read_item(item=command_id, partition_key="rpi-gateway-1")
        item['executed'] = True
        item['command_status'] = "EXECUTED"
        container_commands.replace_item(item=item['id'], body=item)
        return {"status": "Acknowledged"}
    except Exception as e:
        raise HTTPException(status_code=404, detail="Command not found")


# ==========================================
# 4. ENDPOINTS: AUTOMATION RULES
# ==========================================

@app.get("/rules/active")
def get_active_rules():
    query = "SELECT * FROM c WHERE c.is_active = true"
    return list(container_rules.query_items(query=query, enable_cross_partition_query=True))

@app.post("/rules")
def save_rule(rule: dict):
    try:
        container_rules.upsert_item(body=rule)
        return {"status": "Saved", "id": rule.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/rules/{rule_id}/deactivate")
def deactivate_rule(rule_id: str):
    try:
        # Interogare pentru a găsi regula (partition key e id-ul regulii de obicei, sau partition key definit)
        # Simplificare: Presupunem partition key = /id
        item = container_rules.read_item(item=rule_id, partition_key=rule_id)
        item['is_active'] = False
        container_rules.replace_item(item=rule_id, body=item)
        return {"status": "Deactivated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# ==========================================
# 5. ENDPOINTS: ALERTS
# ==========================================

@app.get("/alerts")
def get_alerts():
    if not container_alerts:
        return {"alerts": []}
    
    try:
        alerts = list(container_alerts.query_items(
            query="SELECT TOP 30 * FROM c ORDER BY c.timestamp DESC",
            enable_cross_partition_query=True
        ))
        return {"alerts": alerts}
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return {"alerts": []}

@app.post("/alerts")
def create_alert(alert_data: dict):
    if not container_alerts:
        return {"status": "error", "message": "Alerts not available"}
    
    try:
        alert = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "device_name": alert_data.get("device_name", "Unknown"),
            "issue_type": alert_data.get("issue_type", "Alert"),
            "ai_recommendation": alert_data.get("ai_recommendation", ""),
            "severity": alert_data.get("severity", "info"),
            "technical_data": alert_data.get("technical_data", {}),
            "acknowledged": False
        }
        
        container_alerts.upsert_item(body=alert)
        return {"status": "success", "alert_id": alert["id"]}
    except Exception as e:
        print(f"Error creating alert: {e}")
        return {"status": "error", "message": str(e)}

@app.patch("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    if not container_alerts:
        return {"status": "error", "message": "Alerts not available"}
    
    try:
        alert = container_alerts.read_item(item=alert_id, partition_key=alert_id)
        alert["acknowledged"] = True
        container_alerts.upsert_item(body=alert)
        return {"status": "success", "message": "Alert acknowledged"}
    except Exception as e:
        print(f"Error acknowledging alert: {e}")
        return {"status": "error", "message": str(e)}


# ==========================================
# 6. WATCHDOG (AUTOMATION ENGINE)
# ==========================================

async def automation_watchdog():
    print(" Watchdog activat: Monitorizează senzorii...")
    while True:
        try:
            # 1. Luăm ultima citire de la TOȚI senzorii (simplificat: luăm ultima citire globală)
            # Într-un sistem mare, ai interoga per senzor. Aici luăm ultima valoare intrată în sistem.
            last_readings = list(container_telemetry.query_items(
                query="SELECT TOP 1 * FROM c ORDER BY c._ts DESC",
                enable_cross_partition_query=True
            ))

            # 2. Luăm regulile active
            active_rules = list(container_rules.query_items(
                query="SELECT * FROM c WHERE c.is_active = true",
                enable_cross_partition_query=True
            ))

            if last_readings and active_rules:
                reading = last_readings[0]
                current_sensor = reading.get('sensor_id') # ex: home/sensors/sensor-1
                current_temp = reading.get('temperature')
                current_hum = reading.get('humidity')

                for rule in active_rules:
                    # Verificăm dacă regula e pentru senzorul care tocmai a trimis date
                    if rule.get('sensor_id') == current_sensor:
                        
                        # Verificăm condiția
                        metric = rule.get('trigger_metric') # temperature / humidity
                        operator = rule.get('trigger_condition') # > , < , ==
                        threshold = float(rule.get('trigger_value'))
                        
                        value_to_check = current_temp if metric == 'temperature' else current_hum
                        
                        condition_met = False
                        if operator == '>' and value_to_check > threshold: condition_met = True
                        if operator == '>=' and value_to_check >= threshold: condition_met = True
                        if operator == '<' and value_to_check < threshold: condition_met = True
                        if operator == '<=' and value_to_check <= threshold: condition_met = True
                        if operator == '==' and value_to_check == threshold: condition_met = True

                        if condition_met:
                            # DECLANȘARE!
                            # Convertim path-ul de la sensors la commands
                            command_target = current_sensor.replace("/sensors/", "/commands/")
                            
                            print(f" ALERTA: {metric} {operator} {threshold} pe {current_sensor} -> COMMAND sent!")

                            # Verificăm să nu spamăm comenzi (dacă există deja una PENDING identică)
                            existing = list(container_commands.query_items(
                                query=f"SELECT * FROM c WHERE c.sensor_id = '{command_target}' AND c.command_status = 'PENDING'",
                                enable_cross_partition_query=True
                            ))
                            
                            if not existing:
                                new_cmd = {
                                    "id": str(uuid.uuid4()),
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "gateway_id": "rpi-gateway-1",
                                    "sensor_id": command_target,
                                    "command_status": "PENDING",
                                    "action": rule.get("action", "ACTIVATE_PROCESS"),
                                    "executed": False,
                                    "source": "WATCHDOG_AUTO"
                                }
                                container_commands.upsert_item(body=new_cmd)

        except Exception as e:
            print(f"Eroare Watchdog: {e}")
        
        await asyncio.sleep(5) # Verifică la fiecare 5 secunde


# ==========================================
# 7. DEVICE HEALTH MONITOR (Watchdog Connectivity)
# ==========================================
async def device_health_monitor():
    print("🚑 Device Health Monitor started (Smart Backend Mode)...")
    while True:
        try:
            # 1. Luăm toate dispozitivele înregistrate
            devices = list(container_devices.query_items(
                query="SELECT * FROM c", enable_cross_partition_query=True
            ))
            
            now = datetime.now(timezone.utc)
            
            for dev in devices:
                device_id = dev['id']
                device_type = dev.get('type', 'sensor') # Default sensor
                current_status = dev.get('status')
                
                # --- CAZ 1: GATEWAY ---
                if device_type == 'gateway':
                    last_seen_str = dev.get('timestamp_last_seen')
                    if not last_seen_str: continue 
                    
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str)
                        if last_seen.tzinfo is None: last_seen = last_seen.replace(tzinfo=timezone.utc)
                        delta = (now - last_seen).total_seconds()
                        
                        # Dacă e offline de mult timp (>20s) și era Online
                        if delta > 20 and current_status == 'ONLINE':
                            print(f"💀 Gateway {device_id} died!")
                            dev['status'] = 'OFFLINE'
                            container_devices.upsert_item(dev)
                            
                            # --- ALERTĂ CRITICĂ GATEWAY ---
                            # Backend-ul scrie asta pentru că Gateway-ul e mort
                            if 'container_alerts' in globals() and container_alerts:
                                alert_doc = {
                                    "id": str(uuid.uuid4()),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "sensor_id": device_id,
                                    "alert_type": "Connectivity Lost",
                                    "message": f"Gateway {device_id} is OFFLINE. Check power/network.",
                                    "severity": "CRITICAL", 
                                    "value": 0,
                                    "acknowledged": False
                                }
                                container_alerts.create_item(body=alert_doc)

                    except:
                        continue

                # --- CAZ 2: SENZORI ---
                elif device_type == 'sensor':
                    try:
                        target_id = dev.get('telemetry_topic') 
                        if not target_id: target_id = f"home/sensors/{device_id}" 
                        
                        # --- FOLOSIM TIMESTAMP-UL TĂU (Așa cum ai cerut) ---
                        items = list(container_telemetry.query_items(
                            query=f"SELECT TOP 1 c.timestamp FROM c WHERE c.sensor_id = '{target_id}' ORDER BY c.timestamp DESC",
                            enable_cross_partition_query=True
                        ))
                        
                        is_online = False
                        last_ts_valid = None

                        if items:
                            last_data_ts_str = items[0]['timestamp']
                            try:
                                last_data_ts = datetime.fromisoformat(last_data_ts_str)
                                if last_data_ts.tzinfo is None: last_data_ts = last_data_ts.replace(tzinfo=timezone.utc)
                                delta = (now - last_data_ts).total_seconds()
                                last_ts_valid = last_data_ts_str
                                
                                if delta < 20: 
                                    is_online = True
                            except:
                                pass
                        
                        # LOGICA DE UPDATE STATUS
                        needs_update = False

                        if is_online:
                            if current_status != 'ONLINE':
                                dev['status'] = 'ONLINE'
                                needs_update = True
                                print(f"🟢 Sensor {device_id} is BACK ONLINE")
                            
                            old_ts_str = dev.get('timestamp_last_seen')
                            if not old_ts_str or (datetime.fromisoformat(last_ts_valid) - datetime.fromisoformat(old_ts_str)).total_seconds() > 5:
                                dev['timestamp_last_seen'] = last_ts_valid
                                needs_update = True
                        
                        else:
                            # E OFFLINE
                            if current_status == 'ONLINE':
                                dev['status'] = 'OFFLINE'
                                needs_update = True
                                print(f"🔴 Sensor {device_id} went OFFLINE")

                                # --- ALERTĂ CRITICĂ SENZOR ---
                                # Backend-ul scrie asta pentru că Senzorul nu mai trimite date
                                if 'container_alerts' in globals() and container_alerts:
                                    alert_doc = {
                                        "id": str(uuid.uuid4()),
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "sensor_id": device_id,
                                        "alert_type": "Connectivity Lost",
                                        "message": f"Sensor {device_id} stopped sending data.",
                                        "severity": "CRITICAL", 
                                        "value": 0,
                                        "acknowledged": False
                                    }
                                    container_alerts.create_item(body=alert_doc)
                        
                        if needs_update:
                            container_devices.upsert_item(dev)

                    except Exception as e:
                        print(f"Error checking sensor {device_id}: {e}")

        except Exception as e:
            print(f"Health Monitor Error: {e}")
        
        await asyncio.sleep(5)

# ==========================================
# 8. PORNIRE SERVICII
# ==========================================
@app.on_event("startup")
async def startup_event():
    print("Server Startup Initiated...")

    # Conectam serviciul AI la baza de date
    if container_alerts:
        init_db_containers(container_telemetry, container_alerts)
    
    # Pornim Watchdog-ul simplu (pentru reguli If/Else)
    asyncio.create_task(automation_watchdog())

    # Pornim AI-ul 
    asyncio.create_task(start_ai_loop())

    # Pornim Health monitor 
    asyncio.create_task(device_health_monitor())
    
    print("Background Tasks Started (Watchdog + AI Worker)")