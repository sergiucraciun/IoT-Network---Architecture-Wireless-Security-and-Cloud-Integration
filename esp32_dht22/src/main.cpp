#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <rom/rtc.h>
#include <FS.h>
#include <SPIFFS.h> // <--- Added for Offline Storage

// ==========================================
// 1. HARDWARE CONFIGURATION
// ==========================================
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// ==========================================
// 2. NETWORK CONFIGURATION (PRODUCTION)
// ==========================================
const char* ssid = "IoT_Stable";
const char* password = "Test777@";
const char* mqtt_server = "192.168.20.1";
const int mqtt_port = 8883;

// Topics
const char* TOPIC_LIVE = "home/sensors/sensor-1";   
const char* TOPIC_BULK = "home/offline/sensor-1";   
const char* TOPIC_CMD  = "home/commands/sensor-1";  

// Offline File
const char* FILE_NAME  = "/offline.txt"; 

// ==========================================
// 3. GLOBAL VARIABLES
// ==========================================
unsigned long msg_counter = 0;
int wifi_reconnects = 0;
int mqtt_reconnects = 0;
uint32_t last_heap = 0;
unsigned long last_loop_time = 0;
int last_boot_reason = 0;


// ==========================================
// 4. CERTIFICATE (Raspberry Pi)
// ==========================================
const char* ca_cert =
"-----BEGIN CERTIFICATE-----\n"
"MIIDETCCAfmgAwIBAgIUAJoGpI5fxbnjEj4z6HdNKQsVq6gwDQYJKoZIhvcNAQEL\n"
"BQAwGDEWMBQGA1UEAwwNTXlNb3NxdWl0dG9DQTAeFw0yNTA3MTYyMjIzNDBaFw0z\n"
"NTA3MTQyMjIzNDBaMBgxFjAUBgNVBAMMDU15TW9zcXVpdHRvQ0EwggEiMA0GCSqG\n"
"SIb3DQEBAQUAA4IBDwAwggEKAoIBAQCw5hl9eSnRoPPDoWu/YKZRIukYqtthHBEu\n"
"ExjoI/ARLLuYowEQGmx7mZVSHqocCe0XWFWUtanEEH9kRecHe2X+IK8tGy8U+xqk\n"
"kVik+WIULX76p5yWJqxMLqyufA2DB0+oDkmHUrcA5OkFSlASkKnVITycMpx8ydfF\n"
"A3YpVe8F6JwyaHibZCo9o095+6rouP8h83tFkyH6Zf8M9PexqNeGslUx2joqvX3k\n"
"2hIv1CQDYDQ7tDjQHbLHw9Fh072VLtFN7V+wsO33VXenqW5PAGwK6+Af0BKl0VJM\n"
"1r0rmcJP/kvBoiiS5e0NazAzcPZ9N/JFSW6JuzQzxEG16BDR6f77AgMBAAGjUzBR\n"
"MB0GA1UdDgQWBBSwvv2Y8fSqMPDkZk4DYYtFoVqEYjAfBgNVHSMEGDAWgBSwvv2Y\n"
"8fSqMPDkZk4DYYtFoVqEYjAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUA\n"
"A4IBAQABY3JGA41jK2uPWSO1NMxFVmKoEyK5F/khFm0b5zceULwyC2grng+Mj2j9\n"
"p7XF8hCtEOKSPKzf4DXPjA2oOcyS3IS9EAxoW6POc6ASS2B0aMxkUXt33TAKMN9X\n"
"5vLf3uPfgLyAUR3Jd1dt2QDr3Fl6VxmD+mfXfRNAYVuvO344MzPmh8chVNE7vedN\n"
"zBmbgXtuvx49AFImUz4s9p0NizTR/yUZlwzGI8UKtXweSWJ0Bg1z4e2sE22jm5Rg\n"
"sTgYyVus+bDph2IJFb+a5uFC4ZcgFDeLsZoQT3P6glbOmPBt1wRh9IU53Zwjm1GU\n"
"TrvESiyaXqPCSXh/W2DMa/THsgXg\n"
"-----END CERTIFICATE-----\n";

WiFiClientSecure espClient;
PubSubClient client(espClient);

// ==========================================
// 5. OFFLINE STORAGE FUNCTIONS
// ==========================================

void saveLocal(String data) {
    File f = SPIFFS.open(FILE_NAME, FILE_APPEND);
    if (f) {
        f.println(data);
        f.close();
        Serial.println("💾 Saved Offline (SPIFFS)");
    } else {
        Serial.println("❌ Storage Error");
    }
}

void sendAndClearStorage() {
    if (!SPIFFS.exists(FILE_NAME)) return;

    Serial.println("📂 Found offline data. Syncing...");
    
    File f = SPIFFS.open(FILE_NAME, FILE_READ);
    if (!f) return;

    while (f.available()) {
        String line = f.readStringUntil('\n');
        line.trim();
        
        if (line.length() > 5) {
            client.publish(TOPIC_BULK, line.c_str());
            Serial.println("📤 Synced: " + line);
            client.loop(); 
            delay(50); // Prevent network congestion
        }
    }
    f.close();

    SPIFFS.remove(FILE_NAME);
    Serial.println("🎉 Sync Complete. Storage Cleared.");
}

// ==========================================
// 6. CALLBACK & CONNECTION
// ==========================================

void callback(char* topic, byte* payload, unsigned int length) {
    Serial.println("\n--- MESSAGE RECEIVED ---");
    Serial.print("Topic: "); Serial.println(topic);

    StaticJsonDocument<1024> doc;
    DeserializationError error = deserializeJson(doc, payload, length);

    if (error) {
        Serial.print("JSON Parse Failed: ");
        Serial.println(error.f_str());
        return;
    }

    const char* action = doc["action"];
    Serial.print("Action: "); Serial.println(action);

    if (String(action) == "ACTIVATE_PROCESS") {
        Serial.println(">>> SUCCESS: Activating local IoT process <<<");
    }
    Serial.println("------------------------------------\n");
}

void setup_wifi() {
    delay(10);
    if (WiFi.status() != WL_CONNECTED && millis() > 10000) { wifi_reconnects++; }

    Serial.println("\nConnecting to WiFi...");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500); Serial.print(".");
    }
    Serial.println("\nWiFi Connected. IP: " + WiFi.localIP().toString());
    Serial.print("ESP32 MAC: "); Serial.println(WiFi.macAddress());
}

void reconnect() {
    while (!client.connected()) {
        if (millis() > 10000) { mqtt_reconnects++; }

        Serial.print("Attempting MQTT TLS connection...");
        String clientId = "ESP32-Senzor-1";
        if (client.connect(clientId.c_str())) {
            Serial.println("connected");
            client.subscribe(TOPIC_CMD);
            Serial.println("Subscribed to commands");
        } else {
            Serial.print("failed, rc=");
            Serial.print(client.state());
            delay(5000);
        }
    }
}

// ==========================================
// 7. SETUP
// ==========================================
void setup() {
    Serial.begin(115200);
    dht.begin();

    // Mount SPIFFS (Critical for offline logic)
    if(!SPIFFS.begin(true)){ 
        Serial.println("❌ SPIFFS Mount Failed");
    } else {
        Serial.println("✅ SPIFFS Mounted");
    }

    espClient.setCACert(ca_cert);
    espClient.setHandshakeTimeout(30);

    client.setServer(mqtt_server, mqtt_port);
    client.setCallback(callback);
    client.setBufferSize(1024);
    client.setKeepAlive(60);
    
    setup_wifi();

    last_heap = ESP.getFreeHeap();
    last_boot_reason = rtc_get_reset_reason(0);
}

// ==========================================
// 8. LOOP
// ==========================================
void loop() {
    unsigned long loop_start = millis();
    unsigned long loop_duration = loop_start - last_loop_time;
    last_loop_time = loop_start;

    // Check WiFi first (Auto-reconnect handled by library usually, but good to check)
    if (WiFi.status() != WL_CONNECTED) {
        setup_wifi();
    }

    if (!client.connected()) {
        reconnect();
    }
    client.loop();

    static unsigned long lastMsg = 0;
    if (millis() - lastMsg > 5000) {
        lastMsg = millis();

        float t = dht.readTemperature();
        float h = dht.readHumidity();

        if (!isnan(t) && !isnan(h)) {
            msg_counter++;
            uint32_t current_heap = ESP.getFreeHeap();
            int32_t heap_delta = (int32_t)(current_heap - last_heap);

            // 1. Prepare JSON Document
            StaticJsonDocument<1024> doc;
            doc["temperature"] = t;
            doc["humidity"] = h;
            doc["esp_id"] = "sensor-1";
            doc["esp_ip"] = WiFi.localIP().toString();
            doc["esp_bssid"] = WiFi.BSSIDstr();
            doc["esp_uptime"] = millis() / 1000;
            doc["esp_boot"] = last_boot_reason;
            doc["esp_heap"] = current_heap;
            doc["esp_heap_d"] = heap_delta;
            doc["esp_cpu_t"] = temperatureRead();
            doc["esp_loop"] = loop_duration;
            doc["esp_rssi"] = WiFi.RSSI();
            doc["esp_ch"] = WiFi.channel();
            doc["esp_w_rec"] = wifi_reconnects;
            doc["esp_m_rec"] = mqtt_reconnects;
            doc["esp_msg_c"] = msg_counter;

            char buffer[1024];
            size_t n = serializeJson(doc, buffer);

            bool sent = false;

            // 2. Try to Publish LIVE
            if (client.publish(TOPIC_LIVE, buffer, n)) {
                Serial.println("📡 Data Sent");
                sent = true;

                // If sent successfully, check if we have old data to sync
                if (SPIFFS.exists(FILE_NAME)) {
                    sendAndClearStorage();
                }
            } else {
                Serial.println("⚠️ Publish Failed");
            }

            // 3. If Publish Failed, Save to SPIFFS
            if (!sent) {
                // We save the full JSON string to file for simplicity
                saveLocal(String(buffer)); 
            }

            last_heap = current_heap;
        }
    }
}