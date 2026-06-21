import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

print("Loading dataset...")
try:
    df = pd.read_csv("dataset_final_ai.csv")
except FileNotFoundError:
    print("No dataset found")
    exit()

# --- A. FEATURE ENGINEERING (Calculam Delta/Viteza) ---
df['temp_delta'] = df['temp'].diff().fillna(0)
df['hum_delta']  = df['hum'].diff().fillna(0)
df['heap_delta'] = df['esp_heap'].diff().fillna(0)
df['rssi_var'] = df['esp_rssi'].rolling(window=10).std().fillna(0)

features = ['temp', 'hum', 'temp_delta', 'hum_delta', 'esp_rssi', 'rssi_var', 'esp_heap', 'heap_delta', 'rpi_cpu']

# --- B. CURATARE AUTOMATA (Ca sa invete AI-ul corect) ---
def clean_iqr(df, cols):
    df_c = df.copy()
    for col in cols:
        Q1 = df_c[col].quantile(0.25)
        Q3 = df_c[col].quantile(0.75)
        IQR = Q3 - Q1
        df_c = df_c[(df_c[col] >= Q1 - 2*IQR) & (df_c[col] <= Q3 + 2*IQR)]
    return df_c

df_clean = clean_iqr(df, ['temp_delta', 'heap_delta', 'esp_heap'])
X = df_clean[features]

# --- C. CALCULAM MEDIILE PENTRU REGULA DE 5% ---
# Salvam doar mediile, limitele fixe (20-25) le scriem in Test
stats_baseline = X.mean().to_dict()
joblib.dump(stats_baseline, "stats_baseline.pkl")

# --- D. ANTRENARE AI ---
X_aug = [X]
safe_std = np.maximum(X.std(), 0.01)
for _ in range(3): # Augmentare usoara
    noise = np.random.normal(0, 0.02 * safe_std, X.shape)
    X_aug.append(X + noise)
X_final = pd.concat(X_aug)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_final)

# Contaminare 5% (Destul de relaxat, lasam regulile hard sa faca treaba grea)
model = IsolationForest(n_estimators=300, contamination=0.05, random_state=42)
model.fit(X_scaled)

joblib.dump(model, "ai_model.pkl")
joblib.dump(scaler, "scaler.pkl")

print("Model trained and saved successfully!")