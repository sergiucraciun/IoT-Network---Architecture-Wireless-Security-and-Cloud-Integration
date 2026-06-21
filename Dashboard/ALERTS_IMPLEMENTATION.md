# Alerts Section Implementation

## Overview
Added a complete **Alerts** section to the IoT Dashboard with an Activity Feed design, expandable cards for technical debugging, and severity-based styling.

---

## What Was Added

### 1. **Frontend - HTML (index.html)**

#### Sidebar Link
- Added "Alerts" link in sidebar navigation
- Icon: `notifications_active`
- Placed after Configure section

#### Alerts Template
```html
<template id="alerts-template">
  <div class="main-title">
    <h2>Alerts</h2>
  </div>
  <div class="main-cards">
    <div class="card">
      <div id="alerts-feed" class="alerts-feed">
        <!-- Alerts rendered here -->
      </div>
    </div>
  </div>
</template>
```

---

### 2. **Frontend - CSS (styles.css)**

#### Alert Card Styles
- `.alert-card` - Main card container with left border
- `.alert-card:hover` - Smooth hover animation (translateX)
- `.severity-warning`, `.severity-info`, `.severity-success` - Color variants

#### Alert Components
- `.alert-header` - Device name + timestamp
- `.alert-title` - Bold issue title
- `.alert-timestamp` - Date/time display
- `.alert-recommendation` - AI recommendation text (italic)
- `.alert-actions` - Button container
- `.alert-btn` - Action buttons (Show Data, Acknowledge)
- `.alert-details` - Hidden technical data section
- `.alert-code` - JSON code block (monospace, green text)

#### Features
- Smooth scrollbar with green accent
- Dark theme with transparency
- 600px max-height with overflow
- Responsive design for mobile

---

### 3. **Frontend - JavaScript (scripts.js)**

#### Global State
```javascript
let alertsArray = [];  // Stores all alerts
```

#### Key Functions

**fetchAlertsFromCloud()**
- Fetches alerts from `/alerts` endpoint
- Handles network errors gracefully
- Shows empty state if no alerts

**addAlert(alert)**
- Adds new alert to top of array (newest first)
- Ensures required fields with defaults
- Auto-triggers re-render

**renderAlertsFeed()**
- Renders all alerts as expandable cards
- Shows "No alerts" message when empty
- Creates interactive UI with proper event handlers

**toggleAlertDetails(alertId)**
- Expands/collapses JSON technical data
- Toggles button text dynamically

**acknowledgeAlert(alertId)**
- Sends PATCH request to backend
- Updates local state
- Disables button after acknowledgement

#### Integration
- Alerts link triggers `loadView(alertsTemplate)`
- On page load: calls `fetchAlertsFromCloud()`

---

### 4. **Backend - Python (main.py)**

#### Container Setup
```python
container_alerts = database.get_container_client("alerts")
```

#### New Endpoints

**GET /alerts**
- Returns all alerts sorted by timestamp (newest first)
- Gracefully handles missing container

**POST /alerts**
- Creates new alert with:
  - Auto-generated UUID
  - Current timestamp
  - Device name & issue type
  - AI recommendation
  - Severity level (error, warning, info, success)
  - Technical data (JSON)
  - Acknowledged flag

**PATCH /alerts/{alert_id}/acknowledge**
- Marks alert as acknowledged
- Disables further acknowledgement

---

## Alert Data Structure

```json
{
  "id": "uuid-string",
  "timestamp": "2024-01-15T10:30:45.123456",
  "device_name": "Sensor-1",
  "issue_type": "High Temperature",
  "ai_recommendation": "Check cooling system or reduce ambient temperature",
  "severity": "error",
  "technical_data": {
    "current_temp": 45.2,
    "threshold": 40,
    "trend": "increasing",
    "last_5_readings": [42.1, 43.5, 44.8, 45.2]
  },
  "acknowledged": false
}
```

---

## Severity Colors

| Severity | Border Color | Background | Use Case |
|----------|-------------|-----------|----------|
| `error` | Red (#ff7675) | Red (8% opacity) | Critical issues |
| `warning` | Yellow (#fdcb6e) | Yellow (8% opacity) | Important notices |
| `info` | Blue (#74b9ff) | Blue (8% opacity) | General info |
| `success` | Green (#00b894) | Green (8% opacity) | Resolved/OK status |

---

## Features

✅ **Activity Feed Design**
- Expandable cards with smooth animations
- Newest alerts appear first (LIFO)
- Scrollable list (max 600px)

✅ **Visible Content**
- Device name + Issue type
- AI-generated recommendation
- Timestamp with date & time

✅ **Hidden Content**
- "Show Technical Data" button
- Raw JSON for debugging
- Syntax highlighted (green monospace text)
- Collapsible

✅ **Actions**
- Acknowledge button to mark as read
- Button becomes disabled after acknowledgement
- Toggle technical data visibility

✅ **Empty State**
- Shows "🟢 No alerts" message when feed is empty
- Indicates system health

---

## Usage Example

### Create an Alert (from Backend)
```python
import requests

alert = {
    "device_name": "Sensor-1",
    "issue_type": "Temperature Spike",
    "ai_recommendation": "Check if device is exposed to direct sunlight",
    "severity": "warning",
    "technical_data": {
        "current_value": 38.5,
        "threshold": 35,
        "location": "Living Room"
    }
}

response = requests.post("http://localhost:8000/alerts", json=alert)
```

### Access Alerts
- Navigate to "Alerts" in sidebar
- Alerts load automatically
- Click "Show Technical Data" to expand
- Click "Acknowledge" to mark as read

---

## Testing the Feature

1. **Start Backend**: `uvicorn main:app --reload`
2. **Open Dashboard**: `http://localhost:8000`
3. **Navigate to Alerts**: Click "Alerts" in sidebar
4. **Create Test Alert** (via API or backend):
   ```bash
   curl -X POST http://localhost:8000/alerts \
     -H "Content-Type: application/json" \
     -d '{
       "device_name": "Test-Device",
       "issue_type": "Test Alert",
       "ai_recommendation": "This is a test",
       "severity": "info",
       "technical_data": {"test": true}
     }'
   ```
5. **Verify** alert appears in UI (should be at top)
6. **Expand** technical data
7. **Acknowledge** alert

---

## Files Modified

1. **index.html**
   - Added Alerts sidebar link
   - Added alerts-template

2. **styles.css**
   - Added 150+ lines of alert styling
   - Colors, animations, scrollbars

3. **scripts.js**
   - Added ~150 lines for alert management
   - Functions: fetch, render, toggle, acknowledge
   - Integrated with navigation

4. **main.py**
   - Added alerts container reference
   - Added 3 new endpoints
   - Error handling

---

## Next Steps (Optional)

- [ ] Create alerts automatically from conditions (watchdog integration)
- [ ] Add alert filtering by severity/device
- [ ] Add alert history search
- [ ] Add alert export to CSV
- [ ] Add push notifications for critical alerts
- [ ] Add alert acknowledgement timeout (auto-dismiss)

---

## Notes

- Alerts gracefully degrade if container doesn't exist
- Frontend shows empty state on network errors
- All times shown in user's local timezone
- Newest alerts always appear at top
- Acknowledged alerts remain visible but disabled
