import pandas as pd

# Citim CSV-ul 
df = pd.read_csv("dataset_final_ai.csv")

# Calculam delta exact ca la antrenare
df['temp_delta'] = df['temp'].diff().fillna(0)
df['rssi_var'] = df['esp_rssi'].rolling(window=10).std().fillna(0)
df['heap_delta'] = df['esp_heap'].diff().fillna(0)

print("--- Average Value Learned ---")
print(f"Temp Delta: {df['temp_delta'].mean():.4f}")
print(f"RSSI Var:   {df['rssi_var'].mean():.4f}")
print(f"Heap Delta: {df['heap_delta'].mean():.4f}")
print("-----------------------------------------")





