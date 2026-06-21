# ====================================================================
# Listing 3.Y: Scriptul complet de validare ierarhică a anomaliilor (test_ai.py)
# ====================================================================
import joblib
import pandas as pd
import numpy as np

print("Inițializare motor de testare și încărcare module binare...")
try:
    model = joblib.load("ai_model.pkl")
    scaler = joblib.load("scaler.pkl")
    baseline = joblib.load("stats_baseline.pkl")  # Mediile statistice din laborator
    print("Modulele .pkl au fost încărcate cu succes în memoria RAM.\n")
except Exception as e:
    print(f"Eroare critică la încărcarea modulelor binare: {e}")
    exit()

# Definirea vectorului de caracteristici conform fazei de antrenare
FEATURES = ['temp', 'hum', 'temp_delta', 'hum_delta', 'esp_rssi', 'rssi_var', 'esp_heap', 'heap_delta', 'rpi_cpu']

# --------------------------------------------------------------------
# ⚙️ CONFIGURAREA CRITERIILOR DE FILTRARE (TREPTELE DETERMINISTE)
# --------------------------------------------------------------------
FIXED_RANGES = {
    'temp': (20.0, 25.0),       # Interval fizic admis pentru temperatură
    'hum':  (40.0, 60.0)        # Interval fizic admis pentru umiditate
}

# Parametrii hardware supuși controlului statistic de toleranță directă
DYNAMIC_HARDWARE_COLS = ['esp_rssi', 'esp_heap', 'rpi_cpu']
TOLERANCE_PERCENT = 0.05        # Prag rigid de deviație dinamică (5%)

# --------------------------------------------------------------------
# 🛡️ MOTORUL DE EVALUARE IERARHICĂ A VECTORULUI TELEMETRIC
# --------------------------------------------------------------------
def verifica_anomalie(row_df):
    # --- TREAPA 1: VERIFICARE LIMITE FIXE ---
    for col, (min_val, max_val) in FIXED_RANGES.items():
        val = row_df[col].values[0]
        if val < min_val or val > max_val:
            return {
                "status": "DEPASIRE_LIMITA", 
                "sursa": "LIMITA_FIXA",
                "detalii": f"{col} = {val:.2f} (În afara limitelor fixe {min_val}..{max_val})"
            }

    # --- TREAPTA 2: VERIFICARE LIMITE DINAMICE HARDWARE (REGULA 5%) ---
    for col in DYNAMIC_HARDWARE_COLS:
        val = row_df[col].values[0]
        media = baseline[col]
        
        # Calcularea deviației procentuale permise față de baseline
        limita_delta = abs(media) * TOLERANCE_PERCENT
        
        min_dyn = media - limita_delta
        max_dyn = media + limita_delta
        
        if val < min_dyn or val > max_dyn:
            return {
                "status": "DEV_STATISTICA", 
                "sursa": "REGULA_5%",
                "detalii": f"Parametrul {col} ({val:.1f}) a depășit toleranța de +/- 5% față de medie ({media:.1f})."
            }

    # --- TREAPTA 3: VERIFICARE INTELIGENȚĂ ARTIFICIALĂ (CORELAȚII INCOHERENTE) ---
    # Convertirea și standardizarea vectorului brut utilizând scorul Z stocat
    X_scaled = scaler.transform(row_df[FEATURES])
    
    # Utilizăm funcția predict a modelului Isolation Forest (-1 = Outlier, 1 = Inlier)
    ai_prediction = model.predict(X_scaled)[0]
    score = model.decision_function(X_scaled)[0]
    
    # Dacă algoritmul clasifică pachetul drept outlier structural pe baza celor 9 dimensiuni
    if ai_prediction == -1:
        return {
            "status": "ANOMALIE_STRUCTURALA", 
            "sursa": "MODEL_AI",
            "detalii": f"Corelație imposibilă detectată geometric în spațiul 9D (Scor AI: {score:.4f})"
        }
            
    return {"status": "INLIER_OK", "sursa": "SISTEM", "detalii": "Parametri optimi în regim stabil."}

# --------------------------------------------------------------------
# 🧪 INJECTAREA SCENARIILOR SINTETICE DE TEST
# --------------------------------------------------------------------
# A. Construirea eșantionului de bază perfect normal, utilizând valorile din laborator
row_normal = pd.DataFrame([baseline])

# B. Scenariu de incendiu agresiv -> Forțează declanșarea Treptei 1 (Hard Limits)
row_fire = row_normal.copy()
row_fire['temp'] = 30.0 

# C. Scenariu de Uscare Aer -> Forțează declanșarea Treptei 1 (Hard Limits)
row_dry = row_normal.copy()
row_dry['hum'] = 30.0

# D. Scenariu de Memory Leak major -> Forțează declanșarea Treptei 2 (Regula de 5%)
row_leak = row_normal.copy()
media_heap = baseline['esp_heap']
row_leak['esp_heap'] = media_heap - (media_heap * 0.10)  # Reducere bruscă de 10%

# E. Anomalie de corelație complexă -> Fentează treptele 1 și 2, ajungând direct la Modelul AI
row_ai_anomaly = row_normal.copy()
# Menținem parametrii de stare ficși perfect egali cu mediile lor din laborator (Abatere 0%)
# Forțăm exclusiv deltele pentru a genera o corelație imposibilă în regim de echilibru:
row_ai_anomaly['temp_delta'] = 0.95     # Schimbare termică rapidă, dar sub limita fixă de 1.0
row_ai_anomaly['hum_delta'] = -0.95     # Scădere de umiditate bruscă, dar sub limita fixă de -1.0
row_ai_anomaly['heap_delta'] = -4900.0  # Consum brusc de memorie RAM la nivel de secundă

# --------------------------------------------------------------------
# 🚀 EXECUȚIA ȘI AFIȘAREA REZULTATELOR
# --------------------------------------------------------------------
def rula_scenariu(nume_scenariu, date_intrare):
    rezultat = verifica_anomalie(date_intrare)
    print(f"TEST: {nume_scenariu}")
    print(f"   Rezultat: [{rezultat['status']}]")
    print(f"   Sursa:    {rezultat['sursa']}")
    print(f"   Detalii:  {rezultat['detalii']}\n")

# Evaluarea secvențială a pipeline-ului hibrid
rula_scenariu("Evaluare Regim Standard de Funcționare", row_normal)
rula_scenariu("Simulare Scenariu de Incendiu (30°C)", row_fire)
rula_scenariu("Simulare Scenariu de Uscare Aer (30%)", row_dry)
rula_scenariu("Simulare Scurgere de Memorie / Memory Leak (-10%)", row_leak)
rula_scenariu("Simulare Anomalie de Corelație Subtilă prin AI", row_ai_anomaly)