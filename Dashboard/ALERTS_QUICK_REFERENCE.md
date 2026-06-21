# Alerts Feature - Quick Reference

## Sidebar Navigation
```
Sidebar Links (in order):
├── 📊 Monitor          (monitor-template)
├── 🏠 Sensors          (sensors-template)  
├── ⚙️  Configure        (configure-template)
└── 🔔 Alerts           (alerts-template) ← NEW!
```

## Alert Card Structure (Visible)
```
┌─────────────────────────────────────────┐
│ 🔴 Device-Name • Issue Type    Jan 15   │ ← Header with timestamp
│                                          │
│ "AI recommendation text that             │ ← Recommendation (italic)
│  suggests an action or solution..."      │
│                                          │
│ [Show Technical Data]  [Acknowledge]    │ ← Action buttons
└─────────────────────────────────────────┘
```

## Alert Card Structure (Expanded)
```
┌─────────────────────────────────────────┐
│ 🔴 Device-Name • Issue Type    Jan 15   │
│                                          │
│ "AI recommendation text that             │
│  suggests an action or solution..."      │
│                                          │
│ [Hide Technical Data]  [Acknowledge]    │
│                                          │
│ ┌─────────────────────────────────────┐ │
│ │ {                                   │ │ ← JSON Block (hidden/shown)
│ │   "current_temp": 45.2,             │ │
│ │   "threshold": 40,                  │ │
│ │   "device_id": "sensor-1"           │ │
│ │ }                                   │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Severity Levels & Colors

| Icon | Severity | Border  | Background | Message Color | Use Case |
|------|----------|---------|-----------|---------------|----------|
| 🔴 | error | #ff7675 | Red (8%) | Red | Critical failure |
| 🟠 | warning | #fdcb6e | Yellow (8%) | Orange | Important notice |
| 🔵 | info | #74b9ff | Blue (8%) | Blue | General info |
| 🟢 | success | #00b894 | Green (8%) | Green | Resolved/OK |

## API Endpoints

### GET /alerts
**Purpose:** Fetch all alerts (newest first)

**Response:**
```json
{
  "alerts": [
    {
      "id": "uuid-1",
      "timestamp": "2024-01-15T10:30:45.123456",
      "device_name": "Sensor-1",
      "issue_type": "High Temperature",
      "ai_recommendation": "Check cooling system...",
      "severity": "error",
      "technical_data": { "current": 45.2 },
      "acknowledged": false
    }
  ]
}
```

### POST /alerts
**Purpose:** Create new alert

**Request Body:**
```json
{
  "device_name": "Sensor-1",
  "issue_type": "Temperature Spike",
  "ai_recommendation": "Check if exposed to direct sunlight",
  "severity": "warning",
  "technical_data": {
    "current_value": 38.5,
    "threshold": 35
  }
}
```

**Response:**
```json
{
  "status": "success",
  "alert_id": "uuid-generated"
}
```

### PATCH /alerts/{alert_id}/acknowledge
**Purpose:** Mark alert as acknowledged

**Response:**
```json
{
  "status": "success",
  "message": "Alert acknowledged"
}
```

## JavaScript Functions

### Core Functions
```javascript
fetchAlertsFromCloud()          // Load alerts from API
addAlert(alert)                 // Add new alert to top of list
renderAlertsFeed()              // Render all alerts to UI
toggleAlertDetails(alertId)     // Expand/collapse technical data
acknowledgeAlert(alertId)       // Mark as acknowledged
```

### Global State
```javascript
let alertsArray = [];           // Array of alert objects
```

### Navigation Hook
```javascript
// When user clicks "Alerts" link in sidebar
document.getElementById('alerts-link').addEventListener('click', 
  (e) => { e.preventDefault(); loadView(alertsTemplate); }
);

// Then automatically calls:
fetchAlertsFromCloud();
```

## CSS Classes

**Main Container:**
- `.alerts-feed` - Container for all alerts (scrollable, max-height 600px)

**Alert Card:**
- `.alert-card` - Main card element
- `.alert-card.severity-{warning|info|success}` - Severity styling
- `.alert-card:hover` - Hover animation (translateX 4px)

**Content:**
- `.alert-header` - Flexbox header with title + timestamp
- `.alert-title` - Device name + issue type
- `.alert-timestamp` - Date and time
- `.alert-recommendation` - AI text (italic, lighter color)

**Actions:**
- `.alert-actions` - Button container (flexbox)
- `.alert-btn` - Action buttons
- `.alert-btn:hover` - Button hover effect

**Technical Data:**
- `.alert-details` - Hidden details container (display: none by default)
- `.alert-details.expanded` - Visible when expanded
- `.alert-code` - JSON code block (dark bg, green text)

**Empty State:**
- `.no-alerts` - Message shown when no alerts

## Interaction Flow

```
1. User clicks "Alerts" in sidebar
        ↓
2. loadView(alertsTemplate) called
        ↓
3. fetchAlertsFromCloud() fetches from API
        ↓
4. renderAlertsFeed() creates UI cards
        ↓
5. User sees list of alerts (newest first)
        ├─→ Click "Show Technical Data" → toggleAlertDetails()
        │   └─→ JSON code block expands
        │
        └─→ Click "Acknowledge" → acknowledgeAlert()
            └─→ Button becomes disabled, marked as read
```

## Example Testing Curl Commands

### Create Test Alert
```bash
curl -X POST http://localhost:8000/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "Sensor-1",
    "issue_type": "High Temperature",
    "ai_recommendation": "Check cooling system or move sensor away from heat source",
    "severity": "error",
    "technical_data": {
      "current_temp": 45.2,
      "threshold": 40,
      "location": "Living Room"
    }
  }'
```

### Get All Alerts
```bash
curl http://localhost:8000/alerts
```

### Acknowledge Alert
```bash
curl -X PATCH http://localhost:8000/alerts/ALERT_UUID_HERE/acknowledge
```

## Storage

**Database:** Azure Cosmos DB  
**Container:** `alerts`  
**Partition Key:** `id`  
**Sort:** By `timestamp` (DESC - newest first)

## Features Summary

✅ Activity Feed Design  
✅ Expandable Cards  
✅ JSON Technical Debugging  
✅ Severity Levels with Colors  
✅ Acknowledge/Dismiss  
✅ Timestamps  
✅ Empty State  
✅ Smooth Animations  
✅ Responsive  
✅ Error Handling  

## Integration Points

### With Monitor
- Alerts can be triggered by sensor anomalies detected during polling

### With Configure
- Active conditions can trigger alerts via the watchdog automation

### With Devices
- Each alert linked to specific device (device_name field)

---

**Status:** ✅ Ready for use  
**Last Updated:** Today  
**Version:** 1.0
