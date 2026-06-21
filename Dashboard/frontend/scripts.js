// Variabile Globale
let updateInterval = null; 
let data = [];
let chart = null;
let selectedSensor = "home/sensors/sensor-1"; 
let activeConditions = []; 
let registeredDevices = []; 
let devicesPollInterval = null;

const API_BASE = "https://iot-backend-app-ger.kindbay-166d1581.germanywestcentral.azurecontainerapps.io";


// ==================== 1. SIDEBAR & NAVIGARE ====================
let sidebarOpen = false;
const sidebar = document.getElementById('sidebar');

function openSidebar() {
    if (!sidebarOpen) {
        sidebar.classList.add('sidebar-responsive');
        sidebarOpen = true;
    }
}

function closeSidebar() {
    if (sidebarOpen) {
        sidebar.classList.remove('sidebar-responsive');
        sidebarOpen = false;
    }
}


// ==================== 2. MONITOR (GRAFICE) ====================
async function fetchHistory(limit = 20) {
    try {
        // IMPORTANT: Clear previous data for this sensor switch
        data = [];
        
        const sensorIdEncoded = encodeURIComponent(selectedSensor);
        const res = await fetch(`${API_BASE}/last-readings?sensor_id=${sensorIdEncoded}&limit=${limit}`);
        
        if (!res.ok) {
            console.error(`HTTP error! status: ${res.status}`);
            console.log(`No data available for sensor: ${selectedSensor}`);
            return; 
        }

        const history = await res.json();
        console.log(`📊 Fetched ${history.length} readings for ${selectedSensor}`);

        if (history.length === 0) {
            console.log(`⚠️ No data available for sensor: ${selectedSensor}`);
            // Update card to show "waiting for data"
            const tempEl = document.querySelector('.card h1');
            if (tempEl) tempEl.textContent = 'waiting for data...';
            return;
        }

        data = history.map(item => {
            // 1. Transformăm textul UTC în Obiect Data
            const date = new Date(item.timestamp);
            
            // 2. Browserul calculează automat ora României (HH:MM:SS)
            const timeOnly = date.toLocaleTimeString(undefined, { 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit', 
                hour12: false 
            });
            return { x: timeOnly, y: item.temperature };
        });
        data.reverse();
        
        // IMPORTANT: Update card immediately after fetching
        const latestMsg = history[0];
        const tempEl = document.querySelector('.card h1');
        if (tempEl) tempEl.textContent = `${latestMsg.temperature}°C - ${latestMsg.humidity}%`;
        console.log(`✅ Updated card: ${latestMsg.temperature}°C - ${latestMsg.humidity}%`);

    } catch (err) {
        console.error('Error fetching history:', err);
    }
}

function renderMonitorChart() {
    const chartDiv = document.querySelector("#chart");
    if (!chartDiv) return;
    
    // Handle empty data
    if (!data || data.length === 0) {
        console.log('📊 No data to render chart, showing empty state');
        const options = {
            series: [{ name: 'Temperature', data: [] }],
            chart: {
                id: 'realtime', height: 350, type: 'line', toolbar: { show: false }, zoom: { enabled: false }
            },
            dataLabels: { enabled: false }, 
            stroke: { curve: 'smooth' },
            title: { text: `No data for: ${selectedSensor}`, align: 'left', style: { color: '#ff6b6b' } },
            markers: { size: 0 },
            xaxis: { type: 'category', labels: { style: { colors: '#ffffff' } } },
            yaxis: { min: 0, max: 40, labels: { style: { colors: '#ffffff' } } },
            legend: { show: false },
            tooltip: { theme: 'dark' }
        };
        
        if (chart) chart.destroy();
        chart = new ApexCharts(chartDiv, options); 
        chart.render();
        return;
    }
    
    // Calculate Y-axis limits from actual data
    const temps = data.map(d => d.y);
    const minTemp = Math.floor(Math.min(...temps) - 2);
    const maxTemp = Math.ceil(Math.max(...temps) + 2);

    const options = {
        series: [{ name: 'Temperature', data: data.slice() }],
        chart: {
            id: 'realtime', height: 350, type: 'line', toolbar: { show: false }, zoom: { enabled: false }
        },
        dataLabels: { enabled: false }, 
        stroke: { curve: 'smooth' },
        title: { text: `Data for: ${selectedSensor}`, align: 'left', style: { color: '#ffffff' } },
        markers: { size: 0 },
        xaxis: { type: 'category', labels: { style: { colors: '#ffffff' } } },
        yaxis: { min: minTemp, max: maxTemp, labels: { style: { colors: '#ffffff' } } },
        legend: { show: false },
        tooltip: { theme: 'dark' }
    };

    if (chart) chart.destroy();
    chart = new ApexCharts(chartDiv, options); 
    chart.render();
    console.log(`📈 Chart rendered with ${data.length} data points (${minTemp}°C - ${maxTemp}°C)`);
}

function startPolling() {
    if (updateInterval) clearInterval(updateInterval);
    
    updateInterval = setInterval(async () => {
        try {
            const sensorIdEncoded = encodeURIComponent(selectedSensor);
            const res = await fetch(`${API_BASE}/last-readings?sensor_id=${sensorIdEncoded}&limit=20`); 
            
            if (!res.ok) throw new Error(`HTTP Polling Error: status ${res.status}`);
            
            const history = await res.json();
            
            if (history.length === 0) {
                console.log(`⚠️ No data available during polling for: ${selectedSensor}`);
                return;
            }
            
            data = history.map(item => {
                const date = new Date(item.timestamp);
                const timeOnly = date.toLocaleTimeString(undefined, { 
                    hour: '2-digit', 
                    minute: '2-digit', 
                    second: '2-digit', 
                    hour12: false 
                });
                return { x: timeOnly, y: item.temperature };
            });
            data.reverse();

            if (history.length > 0) {
                const latestMsg = history[0]; 
                const tempEl = document.querySelector('.card h1');
                if (tempEl) tempEl.textContent = `${latestMsg.temperature}°C - ${latestMsg.humidity}%`;
            }

            if (chart) {
                chart.updateSeries([{ 
                    name: 'Temperature', 
                    data: data 
                }]);
            }

        } catch (err) {
            console.error("Polling error:", err);
        }
    }, 5000); 
}

function stopPolling() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
}


// ==================== 3. DEVICE REGISTRY (NOU & IMPORTAT) ====================

// Functie care ia senzorii din Backend
async function fetchAndRenderDevices() {
    try {
        const response = await fetch(`${API_BASE}/devices`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const data = await response.json();
            registeredDevices = data.devices || [];
            console.log('✅ Devices fetched:', registeredDevices);
            
            // Daca suntem in tab-ul Sensors, randam lista vizual
            renderDevicesList(); 
        } else {
            console.error('❌ Failed to fetch devices:', response.status);
        }
    } catch (error) {
        console.error('❌ Network error fetching devices:', error);
    }
}

// Functie care deseneaza lista in Tab-ul Sensors
function renderDevicesList() {
    const listContainer = document.getElementById('registered-devices-list');
    if (!listContainer) return; 

    listContainer.innerHTML = '';

    if (registeredDevices.length === 0) {
        listContainer.innerHTML = '<div class="devices-empty-message">No devices registered yet.</div>';
        return;
    }

    registeredDevices.forEach((device) => {
        const deviceDiv = document.createElement('div');
        deviceDiv.className = 'device-item';

        const infoDiv = document.createElement('div');
        infoDiv.className = 'device-item-info';

        const nameEl = document.createElement('div');
        nameEl.className = 'device-item-name';
        nameEl.textContent = device.friendly_name;

        const detailsEl = document.createElement('div');
        detailsEl.className = 'device-item-details';

        // --- LOGICA STATUS & TIMP ---
        const isOnline = device.status === 'ONLINE';
        const statusColor = isOnline ? '#00b894' : '#ff7675'; // Verde sau Roșu
        
        let statusHtml = `<span style="color:${statusColor}">● ${device.status || 'OFFLINE'}</span>`;
        let timeInfo = "";

        // Afișăm ora DOAR dacă este OFFLINE și avem o dată înregistrată
        if (!isOnline && device.timestamp_last_seen) {
             const dateObj = new Date(device.timestamp_last_seen);
             
             // 1. ORA (Cu secunde)
             const timeStr = dateObj.toLocaleTimeString([], {
                 hour: '2-digit', 
                 minute:'2-digit', 
                 second: '2-digit', 
                 hour12: false
             });
             
             // 2. DATA (Cu An)
             const dateStr = dateObj.toLocaleDateString([], {
                 day: '2-digit', 
                 month: '2-digit', 
                 year: 'numeric'
             });
             
             // Rezultat: (last seen: 14:30:05 - 03/02/2026)
             timeInfo = `<span style="font-size: 11px; opacity: 0.7; margin-left: 5px;">(last seen: ${timeStr} - ${dateStr})</span>`;
        }
        // -----------------------------

        detailsEl.innerHTML = `
            <div><strong>ID:</strong> ${device.id}</div>
            <div><strong>Type:</strong> ${device.type || 'sensor'}</div>
            <div><strong>Loc:</strong> ${device.location}</div>
            <div style="margin-top:5px; font-weight:bold;">
                ${statusHtml} ${timeInfo}
            </div>
        `;

        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'device-item-delete';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', () => deleteDevice(device.id));

        infoDiv.appendChild(nameEl);
        infoDiv.appendChild(detailsEl);
        deviceDiv.appendChild(infoDiv);
        deviceDiv.appendChild(deleteBtn);
        listContainer.appendChild(deviceDiv);
    });
}


// Functie pentru a popula dropdown-ul in Monitor
function populateMonitorSensorDropdown() {
    const select = document.getElementById('monitor-sensor-select');
    if (!select) {
        console.log('⚠️ Dropdown element not found');
        return;
    }

    console.log('📋 Populating dropdown with sensors only:', registeredDevices);

    // 1. Resetăm și punem opțiunea default
    select.innerHTML = '<option value="">-- Choose a sensor --</option>';

    if (!registeredDevices || registeredDevices.length === 0) {
        return; // Lăsăm doar opțiunea default
    }

    let firstValidSensorValue = null;

    // 2. Iterăm și ADĂUGĂM DOAR SENZORII (Filtrăm Gateway-ul)
    registeredDevices.forEach((device) => {
        // --- FILTRU: Ignorăm Gateway-urile ---
        if (device.type === 'gateway') return; 

        const option = document.createElement('option');
        // Folosim topicul sau ID-ul
        option.value = device.telemetry_topic || device.id; 
        // Afișăm nume prietenos
        option.textContent = `${device.friendly_name}`; 
        
        select.appendChild(option);

        // Reținem primul senzor valid găsit (pentru auto-select)
        if (!firstValidSensorValue) {
            firstValidSensorValue = option.value;
        }
    });

    // 3. LOGICA DE SELECȚIE INTELIGENTĂ

    // CAZ A: Avem deja un senzor selectat anterior? (Persistență)
    if (selectedSensor) {
        select.value = selectedSensor;
        // Verificăm dacă senzorul selectat mai există în listă (poate a fost șters)
        if (select.value === "") {
            selectedSensor = null; // Nu mai e valid
        }
    }

    // CAZ B: Nu e nimic selectat, dar avem senzori? Auto-selectăm primul (Ca în codul tău vechi)
    if (!selectedSensor && firstValidSensorValue) {
        selectedSensor = firstValidSensorValue;
        select.value = selectedSensor;
        console.log(` Auto-selected first sensor: ${selectedSensor}`);
        
        // IMPORTANT: Declanșăm manual schimbarea pentru a încărca graficul
        // (Altfel rămâne dropdown-ul selectat dar graficul gol)
        handleSensorSelectionChange(); 
    }
}


// Handle sensor selection change
async function handleSensorSelectionChange(event) {
    const newSensorTopic = event.target.value;
    
    if (!newSensorTopic) {
        console.log('⚠️ No sensor selected');
        return;
    }
    
    if (newSensorTopic === selectedSensor) {
        console.log('ℹ️ Same sensor already selected');
        return;
    }

    console.log(`🔄 Changing sensor from ${selectedSensor} to ${newSensorTopic}`);
    
    // Update global selectedSensor
    selectedSensor = newSensorTopic;

    // Restart polling with new sensor
    stopPolling();
    await fetchHistory();
    renderMonitorChart();
    startPolling();
    
    console.log(`✅ Chart updated for sensor: ${selectedSensor}`);
}

// Functie pentru Inregistrare (ACTUALIZATA)
async function registerDevice() {
    // 1. Preluăm elementele
    const idEl = document.getElementById('device-id');
    const nameEl = document.getElementById('device-name');
    const locEl = document.getElementById('device-location');
    const typeEl = document.getElementById('device-type'); // <--- ELEMENT NOU
    const statusEl = document.getElementById('register-device-status');

    if (!idEl || !nameEl || !locEl || !typeEl) {
        console.error("Missing form elements");
        return;
    }

    const deviceId = idEl.value.trim();
    const deviceName = nameEl.value.trim();
    const deviceLocation = locEl.value.trim();
    const deviceType = typeEl.value; // <--- VALOARE NOUA

    if (!deviceId || !deviceName || !deviceLocation) {
        if (statusEl) statusEl.textContent = 'Please fill in all fields.';
        return;
    }

    if (statusEl) {
        statusEl.textContent = 'Registering...';
        statusEl.style.color = '#fff';
    }

    // 2. Construim obiectul simplu
    // Backend-ul va adauga automat: status="OFFLINE", timestamp_last_seen=null
    const devicePayload = {
        id: deviceId,
        friendly_name: deviceName,
        location: deviceLocation,
        type: deviceType 
    };

    try {
        const response = await fetch(`${API_BASE}/devices`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(devicePayload)
        });

        if (response.ok) {
            const data = await response.json();
            
            if (statusEl) {
                statusEl.textContent = ` Success! ${deviceType} registered.`;
                statusEl.style.color = '#00b894';
            }
            
            // Resetam formularul
            document.getElementById('register-device-form').reset();
            
            // Reincarcam listele
            await fetchAndRenderDevices(); 
            updateConfigureDropdowns(); 

        } else {
            const errorBody = await response.json();
            if (statusEl) {
                statusEl.textContent = `Failed: ${errorBody.detail || 'Error'}`;
                statusEl.style.color = '#ff7675';
            }
        }
    } catch (error) {
        if (statusEl) {
            statusEl.textContent = `Network error: ${error.message}`;
            statusEl.style.color = '#ff7675';
        }
    }
}

// ==================== 4. CONFIGURE & LOGICA DROPDOWN ====================

// Functia care POPULEAZA dropdown-urile in tab-ul Configure
function updateConfigureDropdowns() {
    const manualSelect = document.getElementById('sensor-name');
    const conditionSelect = document.getElementById('condition-sensor-name');

    if (!manualSelect || !conditionSelect) return;

    // Resetam optiunile
    const defaultOption = '<option value="">-- Select Sensor --</option>';
    manualSelect.innerHTML = defaultOption;
    conditionSelect.innerHTML = defaultOption;

    registeredDevices.forEach(device => {
        const option = document.createElement('option');
        
        // Valoarea selectata va fi ID-ul scurt (ex: sensor-1)
        option.value = device.id; 
        option.textContent = `${device.friendly_name} (${device.id})`;
        
        // Stocam topicurile ascunse in dataset ca sa le folosim la trimitere
        option.dataset.telemetry = device.telemetry_topic;
        option.dataset.command = device.command_topic;

        // Adaugam in ambele liste (clonam pentru ca un element DOM nu poate fi in doua locuri)
        manualSelect.appendChild(option.cloneNode(true));
        conditionSelect.appendChild(option); 
    });
}

// Functii Reguli (Rules)
async function loadRulesFromCloud() {
    try {
        const res = await fetch(`${API_BASE}/rules/active`);
        if (res.ok) {
            activeConditions = await res.json();
            renderActiveConditions();
        }
    } catch (err) {
        console.error("Eroare Cloud:", err);
    }
}

function renderActiveConditions() {
    const listContainer = document.getElementById('active-conditions-list');
    if (!listContainer) return;

    listContainer.innerHTML = '';
    if (activeConditions.length === 0) {
        listContainer.innerHTML = '<p style="color: rgba(255,255,255,0.5); font-size:12px;">No active conditions.</p>';
        return;
    }

    activeConditions.forEach((condition, index) => {
        const div = document.createElement('div');
        div.className = 'condition-item';
        div.innerHTML = `
            <div class="condition-item-text">${condition.sensor_id} : ${condition.trigger_metric} ${condition.trigger_condition} ${condition.trigger_value}</div>
        `;
        
        const btn = document.createElement('button');
        btn.className = 'condition-item-delete';
        btn.textContent = 'Delete';
        btn.onclick = () => deleteCondition(index);
        
        div.appendChild(btn);
        listContainer.appendChild(div);
    });
}

async function saveCondition() {
    // Luam elementul SELECT
    const selectEl = document.getElementById('condition-sensor-name');
    const type = document.getElementById('condition-type').value;
    const operator = document.getElementById('condition-operator').value;
    const value = document.getElementById('condition-value').value;
    const statusEl = document.getElementById('condition-form-status');

    if (!selectEl.value || !type || !operator || !value) {
        if (statusEl) statusEl.textContent = 'Fill all fields.';
        return;
    }

    // TRUCUL: Pentru Watchdog, avem nevoie de TELEMETRY TOPIC (home/sensors/...)
    // Il luam din dataset-ul optiunii selectate
    const selectedOption = selectEl.options[selectEl.selectedIndex];
    const telemetryTopic = selectedOption.dataset.telemetry; 

    const newCondition = {
        id: "rule-" + Date.now(),
        timestamp: new Date().toISOString(),
        sensor_id: telemetryTopic, // Trimitem topicul corect catre backend
        trigger_metric: type,
        trigger_condition: operator,
        trigger_value: parseFloat(value),
        action: "ACTIVATE_PROCESS",
        is_active: true
    };

    if (statusEl) statusEl.textContent = 'Saving...';

    try {
        const res = await fetch(`${API_BASE}/rules`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(newCondition)
        });

        if (res.ok) {
            activeConditions.push(newCondition);
            renderActiveConditions();
            if (statusEl) statusEl.textContent = 'Saved!';
            document.getElementById('condition-form').reset();
        } else {
            if (statusEl) statusEl.textContent = 'Error saving.';
        }
    } catch (err) {
        console.error(err);
    }
}

async function deleteCondition(index) {
    const rule = activeConditions[index];
    try {
        await fetch(`${API_BASE}/rules/${rule.id}/deactivate`, { method: 'PATCH' });
        activeConditions.splice(index, 1);
        renderActiveConditions();
    } catch (err) {
        alert("Error deleting.");
    }
}

// Trimitere Comanda Manuala
async function sendControlCommand(commandTopic, actionType) {
    const commandPayload = {
        sensor_id: commandTopic, // Trimitem "home/commands/sensor-1"
        action: actionType
    };

    try {
        const response = await fetch(`${API_BASE}/command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(commandPayload)
        });

        if (response.ok) return { success: true, message: 'Command Sent!' };
        else return { success: false, message: 'Failed.' };
    } catch (error) {
        return { success: false, message: 'Network error.' };
    }
}

// ==================== 5. ALERTS & ACTIVITY FEED ====================
let alertsArray = [];
let alertPollInterval = null; 

// "memorie" care tine minte ce ID-uri sunt deschise in show details
let expandedAlertIds = new Set();

// 1. Funcții de Polling (Actualizare automată)
function startAlertPolling() {
    if (alertPollInterval) clearInterval(alertPollInterval);
    
    console.log("🔄 Alert polling started...");
    alertPollInterval = setInterval(async () => {
        await fetchAlertsFromCloud();
    }, 2000); 
}

function stopAlertPolling() {
    if (alertPollInterval) {
        clearInterval(alertPollInterval);
        alertPollInterval = null;
        console.log("🛑 Alert polling stopped.");
    }
}

// 2. Fetch alerts from cloud
async function fetchAlertsFromCloud() {
    try {
        const response = await fetch(`${API_BASE}/alerts`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const alertsData = await response.json();
            alertsArray = alertsData.alerts || [];
            renderAlertsFeed();
        } else {
            console.error('❌ Failed to fetch alerts:', response.status);
        }
    } catch (error) {
        console.error('❌ Network error fetching alerts:', error);
    }
}


// 3. Render all alerts in the feed
function renderAlertsFeed() {
    const feedContainer = document.getElementById('alerts-feed');
    if (!feedContainer) return;

    // Salvam pozitia scroll-ului
    const scrollPos = feedContainer.scrollTop;

    feedContainer.innerHTML = '';

    if (alertsArray.length === 0) {
        feedContainer.innerHTML = '<div class="no-alerts">🟢 No alerts at the moment. System running smoothly!</div>';
        return;
    }

    alertsArray.forEach((alert) => {

        // --- 1. CALCULARE TIMP ---
        const alertDate = new Date(alert.timestamp);
        const timeStr = alertDate.toLocaleTimeString(undefined, { 
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false 
        });
        const dateStr = alertDate.toLocaleDateString(undefined, { 
            day: 'numeric', month: 'short' 
        });

        // --- 2. LOGICA CULORI (CORECTATĂ) ---
        let severityClass = 'severity-info';
        let borderColors = '#0984e3'; // Default: Albastru (INFO)
        let icon = '🔵'; 
        const severityUpper = (alert.severity || 'INFO').toUpperCase();

        // Galben (WARNING) - Anomalii persistente (4+)
        if (alert.severity === 'WARNING') {
            borderColors = '#fdcb6e'; 
            icon = '🟡';
            severityClass = 'severity-warning';
        }
        
        // Roșu (CRITICAL) - EXCLUSIV Offline
        if (alert.severity === 'CRITICAL') {
            borderColors = '#ff7675'; 
            icon = '🔴';
            severityClass = 'severity-critical';
        }

        // --- 3. CREARE ELEMENT (CORECTATĂ) ---
        // Mai întâi creăm elementul, apoi aplicăm stilul!
        const alertCard = document.createElement('div');
        alertCard.className = `alert-card ${severityClass}`;
        alertCard.id = `alert-${alert.id}`;
        alertCard.style.borderLeft = `4px solid ${borderColors}`; // Aici era greșeala cu alertDiv

        // --- 4. HEADER (Mapat pe datele din Python) ---
        const header = document.createElement('div');
        header.className = 'alert-header';
        // Folosim sensor_id sau device_name ca fallback
        const name = alert.sensor_id || alert.device_name || 'Device';
        // Folosim alert_type sau issue_type ca fallback
        const type = alert.alert_type || alert.issue_type || 'Alert';
        
        header.innerHTML = `
            <h3 class="alert-title">${icon} ${name} • ${type}</h3>
            <span class="alert-timestamp">${dateStr} ${timeStr}</span>
        `;

        // --- 5. MESAJ (Mapat pe datele din Python) ---
        const recommendation = document.createElement('div');
        recommendation.className = 'alert-recommendation';
        // Folosim message sau ai_recommendation ca fallback
        recommendation.textContent = alert.message || alert.ai_recommendation || 'No details provided.';

        // --- 6. ACTIONS (Păstrat identic cu codul tău) ---
        const actions = document.createElement('div');
        actions.className = 'alert-actions';
        
        // BUTONUL SHOW/HIDE DETAILS
        const isExpanded = expandedAlertIds.has(alert.id);
        const detailsBtn = document.createElement('button');
        detailsBtn.className = 'alert-btn';
        detailsBtn.textContent = isExpanded ? 'Hide Technical Data' : 'Show Technical Data';
        detailsBtn.onclick = () => toggleAlertDetails(alert.id);

        // BUTONUL COPY JSON
        const copyBtn = document.createElement('button');
        copyBtn.className = 'alert-btn';
        copyBtn.innerHTML = '📋 Copy JSON';
        copyBtn.style.marginLeft = '10px';
        copyBtn.style.marginRight = '10px';
        
        copyBtn.onclick = () => {
            // Folosim technical_data sau întregul alert object dacă lipsește
            const dataToCopy = alert.technical_data || alert;
            const jsonText = JSON.stringify(dataToCopy, null, 2);
            navigator.clipboard.writeText(jsonText).then(() => {
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '✅ Copied!';
                copyBtn.style.backgroundColor = '#00b894';
                copyBtn.style.color = '#fff';

                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                    copyBtn.style.backgroundColor = '';
                    copyBtn.style.color = '';
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy:', err);
            });
        };

        // BUTONUL ACKNOWLEDGE
        const dismissBtn = document.createElement('button');
        dismissBtn.className = 'alert-btn';
        dismissBtn.textContent = alert.acknowledged ? 'Acknowledged' : 'Acknowledge';
        dismissBtn.style.opacity = alert.acknowledged ? '0.5' : '1';
        dismissBtn.disabled = alert.acknowledged;
        // Colorăm butonul în funcție de severitate pentru aspect plăcut
        dismissBtn.style.color = borderColors; 
        dismissBtn.style.borderColor = borderColors;
        
        dismissBtn.onclick = () => acknowledgeAlert(alert.id);

        actions.appendChild(detailsBtn);
        actions.appendChild(copyBtn);
        actions.appendChild(dismissBtn);

        // --- 7. DETAILS BLOCK (Păstrat identic) ---
        const details = document.createElement('div');
        details.className = 'alert-details';
        details.id = `details-${alert.id}`;
        
        if (isExpanded) {
            details.classList.add('expanded');
        }
        
        const codeBlock = document.createElement('div');
        codeBlock.className = 'alert-code';
        
        const codeEl = document.createElement('code');
        // Folosim technical_data sau fallback
        const techData = alert.technical_data || alert; 
        codeEl.textContent = JSON.stringify(techData, null, 2);
        
        codeBlock.appendChild(codeEl);
        details.appendChild(codeBlock);

        // Asamblare Finală
        alertCard.appendChild(header);
        alertCard.appendChild(recommendation);
        alertCard.appendChild(actions);
        alertCard.appendChild(details);

        feedContainer.appendChild(alertCard);
    });

    if (alertsArray.length > 0) {
        feedContainer.scrollTop = scrollPos;
    }
}


// 4. Toggle technical data visibility
function toggleAlertDetails(alertId) {
    const detailsEl = document.getElementById(`details-${alertId}`);
    
    if (expandedAlertIds.has(alertId)) {
        expandedAlertIds.delete(alertId); 
    } else {
        expandedAlertIds.add(alertId); 
    }

    if (detailsEl) {
        detailsEl.classList.toggle('expanded');
        
        const btn = detailsEl.parentElement.parentElement.querySelector('.alert-btn');
        if (btn && btn.textContent.includes('Technical Data')) {
            btn.textContent = detailsEl.classList.contains('expanded') 
                ? 'Hide Technical Data' 
                : 'Show Technical Data';
        }
    }
}

// 5. Acknowledge alert
async function acknowledgeAlert(alertId) {
    try {
        const response = await fetch(`${API_BASE}/alerts/${alertId}/acknowledge`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const alert = alertsArray.find(a => a.id === alertId);
            if (alert) {
                alert.acknowledged = true;
                renderAlertsFeed();
            }
        }
    } catch (error) {
        console.error('Error acknowledging alert:', error);
    }
}


// --- FUNCȚII PENTRU ACTUALIZARE AUTOMATĂ LISTA DISPOZITIVE ---

function startDevicesPolling() {
    if (devicesPollInterval) clearInterval(devicesPollInterval);
    
    console.log("🔄 Devices list polling started...");
    // Verificăm la fiecare 3 secunde
    devicesPollInterval = setInterval(async () => {
        // Apelăm funcția care ia datele și redesenează lista
        await fetchAndRenderDevices(); 
    }, 3000); 
}

function stopDevicesPolling() {
    if (devicesPollInterval) {
        clearInterval(devicesPollInterval);
        devicesPollInterval = null;
        console.log("🛑 Devices list polling stopped.");
    }
}


// ==================== 6. INITIALIZARE (MAIN) ====================
document.addEventListener('DOMContentLoaded', async () => {
    // Incarcam datele initiale
    loadRulesFromCloud();
    
    // Incarcam dispozitivele o singura data la inceput
    await fetchAndRenderDevices(); 

    const mainContainer = document.querySelector('.main-container');
    const menuToggle = document.getElementById('menu-toggle'); 
    const closeSidebarBtn = document.getElementById('close-sidebar');

    const monitorTemplate = document.getElementById('monitor-template');
    const sensorsTemplate = document.getElementById('sensors-template');
    const configureTemplate = document.getElementById('configure-template');
    const alertsTemplate = document.getElementById('alerts-template');

    // Functia de Navigare (ROUTER-UL APLICATIEI)
    async function loadView(template) {
        // 1. OPRIM ORICE POLLING ANTERIOR (CURATENIE)
        stopPolling();      // Oprește graficul din Monitor
        stopAlertPolling(); // Oprește feed-ul din Alerts <--- ADAUGAT
        stopDevicesPolling();

        mainContainer.innerHTML = '';
        mainContainer.appendChild(template.content.cloneNode(true));

        // --- LOGICA PENTRU MONITOR ---
        if (template.id === 'monitor-template') {
            await fetchAndRenderDevices();
            populateMonitorSensorDropdown();
            
            const sensorSelect = document.getElementById('monitor-sensor-select');
            if (sensorSelect) {
                sensorSelect.addEventListener('change', handleSensorSelectionChange);
                // Păstrăm selecția anterioară dacă există
                if (selectedSensor) sensorSelect.value = selectedSensor;
            }
            
            await fetchHistory();
            renderMonitorChart();
            startPolling(); // Pornim polling-ul pentru Grafic
        }
        
        // --- LOGICA PENTRU SENSORS ---
        if (template.id === 'sensors-template') {
            await fetchAndRenderDevices();
            startDevicesPolling();         
        }

        // --- LOGICA PENTRU CONFIGURE ---
        if (template.id === 'configure-template') {
            renderActiveConditions();
            updateConfigureDropdowns();
        }

        // --- LOGICA PENTRU ALERTS ---
        if (template.id === 'alerts-template') {
            await fetchAlertsFromCloud(); // Încărcare inițială
            startAlertPolling();          // Pornim polling-ul pentru Alerte (Live Update) <--- ADAUGAT
        }
    }

    
    // Sidebar Listeners
    if (menuToggle) menuToggle.addEventListener('click', openSidebar);
    if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);

    // Navigation Listeners
    document.getElementById('monitor-link').addEventListener('click', (e) => { e.preventDefault(); loadView(monitorTemplate); });
    document.getElementById('sensors-link').addEventListener('click', (e) => { e.preventDefault(); loadView(sensorsTemplate); });
    document.getElementById('configure-link').addEventListener('click', (e) => { e.preventDefault(); loadView(configureTemplate); });
    document.getElementById('alerts-link').addEventListener('click', (e) => { e.preventDefault(); loadView(alertsTemplate); });

    // --- EVENT DELEGATION PENTRU BUTOANE DINAMICE ---
    document.addEventListener('click', async (e) => {
        
        // 1. BUTON ACTIVATE COMMAND (MANUAL)
        if (e.target.classList.contains('btn-danger') && e.target.textContent.trim() === 'Activate command') {
            e.preventDefault();
            const form = e.target.closest('form');
            const select = form.querySelector('select[name="sensorName"]'); 
            const statusEl = form.querySelector('#sensor-config-status');
            
            if (!select.value) {
                statusEl.textContent = 'Select a sensor first.';
                return;
            }

            const selectedOption = select.options[select.selectedIndex];
            const commandTopic = selectedOption.dataset.command; 

            statusEl.textContent = 'Sending...';
            const result = await sendControlCommand(commandTopic, 'ACTIVATE_PROCESS');
            statusEl.textContent = result.message;
        }

        // 2. BUTON REGISTER DEVICE
        if (e.target.id === 'register-device-btn') {
            e.preventDefault();
            registerDevice();
        }

        // 3. BUTON SAVE CONDITION
        if (e.target.id === 'save-condition-btn') {
            e.preventDefault();
            saveCondition();
        }
    });

    // Incarcam prima pagina (Monitor)
    loadView(monitorTemplate);
});