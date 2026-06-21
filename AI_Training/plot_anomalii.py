import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
# Importăm StandardScaler pentru că PCA are nevoie de date la aceeași scară
from sklearn.preprocessing import StandardScaler
# Importăm algoritmul de reducere a dimensiunii de la 9D la 2D
from sklearn.decomposition import PCA

print("Se încarcă setul de date...")
df = pd.read_csv("dataset_final_ai.csv")

# 1. Feature Engineering exact ca în train_ai.py
df['temp_delta'] = df['temp'].diff().fillna(0)
df['hum_delta']  = df['hum'].diff().fillna(0)
df['heap_delta'] = df['esp_heap'].diff().fillna(0)
df['rssi_var']   = df['esp_rssi'].rolling(window=10).std().fillna(0)

features = ['temp', 'hum', 'temp_delta', 'hum_delta', 'esp_rssi', 'rssi_var', 'esp_heap', 'heap_delta', 'rpi_cpu']
df_clean = df.dropna(subset=['rssi_var']).copy()

# 2. Antrenare Isolation Forest cu contaminare de 5%
clf = IsolationForest(contamination=0.05, random_state=42)
df_clean['anomaly_code'] = clf.fit_predict(df_clean[features])

normale = df_clean[df_clean['anomaly_code'] == 1]
anomalii = df_clean[df_clean['anomaly_code'] == -1]

# ==========================================
# GRAFICUL 1: MEDIU ȘI REȚEA
# ==========================================
plt.figure(figsize=(10, 6), dpi=300)
plt.scatter(anomalii['temp'], anomalii['esp_rssi'], c='red', label='Anomalii (Outliers)', s=15, alpha=1.0, zorder=1)
plt.scatter(normale['temp'], normale['esp_rssi'], c='blue', label='Date Normale (Inliers)', s=15, alpha=1.0, zorder=2)
plt.title('Detecția Anomaliilor - Puterea Semnalului și Temperatura Absolută', fontsize=12, pad=15)
plt.xlabel('Temperatura Absolută (°C)', fontsize=10)
plt.ylabel('Puterea Semnalului Radio - esp_rssi (dBm)', fontsize=10)
plt.grid(True, linestyle='--', alpha=0.3)
plt.legend(loc='lower left')
plt.tight_layout()
plt.savefig('grafic_mediu.png')
plt.close()

# ==========================================
# GRAFICUL 2: SĂNĂTATE HARDWARE
# ==========================================
plt.figure(figsize=(10, 6), dpi=300)
plt.scatter(anomalii['esp_heap'], anomalii['rpi_cpu'], c='red', label='Anomalii (Outliers)', s=15, alpha=1.0, zorder=1)
plt.scatter(normale['esp_heap'], normale['rpi_cpu'], c='blue', label='Date Normale (Inliers)', s=15, alpha=1.0, zorder=2)
plt.title('Detecția Anomaliilor - RAM ESP32 și Procesor Raspberry', fontsize=12, pad=15)
plt.xlabel('Memorie RAM Disponibilă pe Microcontroler - esp_heap (Bytes)', fontsize=10)
plt.ylabel('Încărcare Procesor Gateway - rpi_cpu (%)', fontsize=10)
plt.grid(True, linestyle='--', alpha=0.3)
plt.legend(loc='upper left')
plt.tight_layout()
plt.savefig('grafic_hardware.png')
plt.close()

# ==========================================
# NEW -> GRAFICUL 3: TRANSPUNEREA GLOBALĂ 9D -> 2D (PCA)
# ==========================================
print("Se execută transpunerea spațiului 9D în plan bidimensional prin PCA...")

# Standardizăm datele (PCA funcționează corect doar pe date scalate)
scaler_pca = StandardScaler()
features_scaled = scaler_pca.fit_transform(df_clean[features])

# Reducem de la 9 dimensiuni la exact 2 componente principale
pca = PCA(n_components=2, random_state=42)
features_2d = pca.fit_transform(features_scaled)

# Salvăm noile coordonate virtuale în tabel
df_clean['PC1'] = features_2d[:, 0]
df_clean['PC2'] = features_2d[:, 1]

# Actualizăm selecțiile pentru înliers și outliers cu noile coordonate PCA
normale_pca = df_clean[df_clean['anomaly_code'] == 1]
anomalii_pca = df_clean[df_clean['anomaly_code'] == -1]

plt.figure(figsize=(10, 6), dpi=300)
# Desenăm mai întâi punctele roșii (anomaliile globale), apoi cele albastre (datele normale)
plt.scatter(anomalii_pca['PC1'], anomalii_pca['PC2'], c='red', label='Anomalii Globale (Outliers)', s=15, alpha=1.0, zorder=1)
plt.scatter(normale_pca['PC1'], normale_pca['PC2'], c='blue', label='Stare Normală Globală (Inliers)', s=15, alpha=1.0, zorder=2)

plt.title('Harta Globală a Anomaliilor - Transpunerea Spațiului multidimensional (9D)', fontsize=12, pad=15)
plt.xlabel('Componenta Spațială Virtuală 1 (PC1)', fontsize=10)
plt.ylabel('Componenta Spațială Virtuală 2 (PC2)', fontsize=10)
plt.grid(True, linestyle='--', alpha=0.3)
plt.legend(loc='upper right')
plt.tight_layout()
plt.savefig('grafic_global_pca.png')
plt.close()

print("Toate cele trei grafice au fost salvate cu succes!")