import asyncio
import joblib
import pandas as pd
import logging
import os
import uuid
from datetime import datetime, timezone
from azure.cosmos import CosmosClient
from concurrent.futures import ThreadPoolExecutor

# Configurare Logger
logger = logging.getLogger("AI-Service")
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------
# CONFIGURARE GLOBALA
# ---------------------------------------------------------
container_telemetry = None
container_alerts = None

# Thread separat pentru calcule
ai_thread_pool = ThreadPoolExecutor(max_workers=1)

# MEMORIA INTERNA (RAM) - Counterul pentru logica 2 Galbene -> 1 Roșu
consecutive_anomalies = {} 

model = None
scaler = None
baseline = None
AI_AVAILABLE = False

# Încărcare Modele
try:
    if os.path.exists("ai_model.pkl"):
        model = joblib.load("ai_model.pkl")
        scaler = joblib.load("scaler.pkl")
        baseline = joblib.load("stats_baseline.pkl")
        AI_AVAILABLE = True
        logger.info("AI Models Loaded.")
    else:
        logger.warning(".pkl files not found. Running in basic mode.")
except Exception as e:
    logger.error(f"AI Load Error: {e}")

FEATURES = ['temp', 'hum', 'temp_delta', 'hum_delta', 'esp_rssi', 'rssi_var', 'esp_heap', 'heap_delta', 'rpi_cpu']

# LIMITE FIXE
FIXED_RANGES = {
    'temp': (20.0, 25.0),
    'hum':  (40.0, 60.0),
    'temp_delta': (-1.0, 1.0),
    'hum_delta':  (-1.0, 1.0)
}
TOLERANCE_PERCENT = 0.05

# ---------------------------------------------------------
# 1. INITIALIZARE
# ---------------------------------------------------------
def init_db_containers(telemetry, alerts):
    global container_telemetry, container_alerts
    container_telemetry = telemetry
    container_alerts = alerts

# ---------------------------------------------------------
# 2. ANALIZA MATEMATICĂ (Returnează tipul anomaliei)
# ---------------------------------------------------------
def analyze_data_sync(data_row, model_ref, scaler_ref, baseline_ref):
    try:
        df_row = pd.DataFrame([data_row])
        df_row = df_row[FEATURES]

        # =========================================================
        # NIVEL 1: HARD LIMITS (Siguranță Critică)
        # =========================================================
        for col, (min_val, max_val) in FIXED_RANGES.items():
            val = data_row.get(col, 0)
            if val < min_val or val > max_val:
                return {"is_anomaly": True, "type": "HARD_LIMIT", "details": f"{col} out of range"}

        # =========================================================
        # NIVEL 2: BASELINE (STATISTICA)
        # =========================================================
        if baseline_ref:
            for col in FEATURES:
                val = data_row.get(col, 0)
                
                # --- FILTRE DE ZGOMOT (Noise Filters) ---
                if col == 'rssi_var' and val < 3.0: continue
                if col == 'esp_rssi': continue 
                if col == 'rpi_cpu' and val < 50.0: continue
                if col == 'temp_delta' and abs(val) < 0.5: continue
                if col == 'hum_delta' and abs(val) < 3.0: continue
                if col == 'heap_delta' and abs(val) < 1000: continue
                # -----------------------------------------

                if col not in FIXED_RANGES:
                    media = baseline_ref.get(col, 0)
                    limit = max(abs(media) * TOLERANCE_PERCENT, 1.0)
                    
                    if abs(val - media) > limit:
                        return {"is_anomaly": True, "type": "STATISTICAL", "details": f"{col} deviation"}

        # =========================================================
        # NIVEL 3: AI (Isolation Forest)
        # =========================================================
        if model_ref and scaler_ref:
            X_scaled = scaler_ref.transform(df_row)
            prediction = model_ref.predict(X_scaled)[0]
            
            if prediction == -1:
                # --- VERIFICARE SEMANTICĂ ---
                is_rssi_noise = data_row.get('rssi_var', 0) < 3.0
                is_temp_noise = abs(data_row.get('temp_delta', 0)) < 0.5
                is_hum_noise  = abs(data_row.get('hum_delta', 0)) < 3.0
                is_cpu_noise  = data_row.get('rpi_cpu', 0) < 50.0
                is_heap_noise = abs(data_row.get('heap_delta', 0)) < 1000

                has_real_issue = False
                if not is_rssi_noise: has_real_issue = True
                if not is_temp_noise: has_real_issue = True
                if not is_hum_noise:  has_real_issue = True
                if not is_cpu_noise:  has_real_issue = True
                if not is_heap_noise: has_real_issue = True

                if not has_real_issue:
                    return {"is_anomaly": False}

                return {
                    "is_anomaly": True, 
                    "type": "AI_ANOMALY", 
                    "details": "Unusual Complex Pattern (AI)"
                }

        return {"is_anomaly": False}

    except Exception as e:
        logger.error(f"Math Error: {e}")
        return {"is_anomaly": False}

# ---------------------------------------------------------
# 3. BUCLA PRINCIPALĂ
# ---------------------------------------------------------
async def start_ai_loop():
    logger.info("AI Loop Started (1s interval)")
    loop = asyncio.get_running_loop()

    while True:
        try:
            # Așteptăm conexiunea la DB
            if not container_telemetry:
                await asyncio.sleep(5)
                continue

            # Luăm datele neprocesate
            query = "SELECT * FROM c WHERE NOT IS_DEFINED(c.ai_checked) ORDER BY c.timestamp DESC OFFSET 0 LIMIT 10"
            items = list(container_telemetry.query_items(query=query, enable_cross_partition_query=True))

            if not items:
                await asyncio.sleep(1) 
                continue

            for item in items:
                sensor_id = item.get('sensor_id', 'unknown')
                
                # Pregătire date
                data_row = {
                    'temp': float(item.get('temperature', 0)),
                    'hum': float(item.get('humidity', 0)),
                    'temp_delta': float(item.get('temp_delta', 0)),
                    'hum_delta': float(item.get('hum_delta', 0)),
                    'esp_rssi': float(item.get('esp_rssi', -60)),
                    'rssi_var': float(item.get('rssi_var', 0)),
                    'esp_heap': float(item.get('esp_heap', 0)),
                    'heap_delta': float(item.get('heap_delta', 0)),
                    'rpi_cpu': float(item.get('rpi_cpu', 0)), 
                }

                # Analiza (Executată în thread separat)
                result = await loop.run_in_executor(
                    ai_thread_pool, 
                    analyze_data_sync, 
                    data_row, model, scaler, baseline
                )

                # --- LOGICA CRITICĂ PENTRU ALERTE (MODIFICATĂ) ---
                current_count = 0
                severity = "INFO" # Default Albastru
                should_alert = False
                alert_msg = ""

                if result['is_anomaly']:
                    current_count = consecutive_anomalies.get(sensor_id, 0) + 1
                    consecutive_anomalies[sensor_id] = current_count 
                    
                    should_alert = True
                    
                    # === LOGICA TA DE CULORI AICI ===
                    if current_count <= 3:
                        severity = "INFO"    # 🔵 1, 2, 3 -> ALBASTRU
                        alert_msg = f"Potential Anomaly ({current_count}/3): {result['details']}"
                    else:
                        severity = "WARNING" # 🟡 4+ -> GALBEN
                        alert_msg = f"Persistent Issue ({current_count} in a row): {result['details']}"
                        
                else:
                    # Resetăm contorul dacă totul e normal
                    consecutive_anomalies[sensor_id] = 0
                    current_count = 0
                    should_alert = False

                # --- UPDATE TELEMETRY (Marcăm ca verificat) ---
                item['ai_checked'] = True
                item['is_anomaly'] = result['is_anomaly']
                item['in_a_row'] = current_count 
                container_telemetry.upsert_item(item)

                # --- UPDATE ALERTS (Scriem alerta dacă e cazul) ---
                if should_alert:
                    alert_doc = {
                        "id": str(uuid.uuid4()),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "sensor_id": sensor_id,       # <--- NUME CORECT PENTRU FRONTEND
                        "alert_type": result['type'], # <--- NUME CORECT PENTRU FRONTEND
                        "message": alert_msg,         # <--- NUME CORECT PENTRU FRONTEND
                        "severity": severity,         # INFO sau WARNING
                        "technical_data": data_row,
                        "acknowledged": False,
                        "in_a_row": current_count
                    }
                    container_alerts.upsert_item(body=alert_doc)
                    logger.warning(f"{sensor_id}: {severity} ({current_count} in a row)")

        except Exception as e:
            logger.error(f"Loop Error: {e}")
            await asyncio.sleep(5)
        
        await asyncio.sleep(1)