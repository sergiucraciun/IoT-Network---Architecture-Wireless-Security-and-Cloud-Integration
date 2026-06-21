# Device Registry Implementation Guide

## Overview
The Sensors section has been completely redesigned to include a dynamic Device Registry system. Users can now register, view, and delete IoT devices from a centralized interface.

## UI Changes

### HTML Structure (sensors-template)

**Card 1: Register New Device**
- Device ID input (e.g., sensor-1) - Primary key
- Friendly Name input (e.g., Living Room Sensor)
- Location/Description input
- Register Device button (btn-primary)
- Status message display

**Card 2: Registered Devices**
- Dynamic list container for all registered devices
- Each device shows:
  - Friendly Name (bold)
  - Device ID
  - Location
  - Telemetry Topic (auto-generated)
  - Delete button (btn-danger)
- Empty state message when no devices exist

## CSS Classes Added

```css
.registered-devices-list         /* Main container for devices */
.device-item                     /* Individual device card */
.device-item-info                /* Device info section */
.device-item-name                /* Device friendly name */
.device-item-details             /* Device details text */
.device-item-delete              /* Delete button styling */
.devices-empty-message           /* Empty state message */
```

## JavaScript Functions

### 1. `registerDevice()`
- **Triggered by**: "Register Device" button click
- **Input validation**: Checks all fields are filled
- **Auto-generates MQTT topics**:
  - `telemetry_topic`: `home/sensors/{device_id}`
  - `command_topic`: `home/commands/{device_id}`
- **Sends POST request** to `{API_BASE}/devices`
- **Payload format**:
```json
{
  "id": "sensor-1",
  "friendly_name": "Living Room Sensor",
  "location": "North Wall",
  "telemetry_topic": "home/sensors/sensor-1",
  "command_topic": "home/commands/sensor-1"
}
```
- **After success**: Resets form and reloads devices list

### 2. `fetchAndRenderDevices()`
- **Called when**: Sensors template loads (via loadView)
- **Sends GET request** to `{API_BASE}/devices`
- **Expected response format**:
```json
{
  "devices": [
    {
      "id": "sensor-1",
      "friendly_name": "Living Room Sensor",
      "location": "North Wall",
      "telemetry_topic": "home/sensors/sensor-1",
      "command_topic": "home/commands/sensor-1"
    }
  ]
}
```
- **Calls**: `renderDevicesList()` to display results

### 3. `renderDevicesList()`
- **Displays** all devices from `registeredDevices` array
- **Shows empty message** if no devices exist
- **Creates device cards** with all details
- **Attaches delete listeners** to each Delete button

### 4. `deleteDevice(deviceId)`
- **Triggered by**: Delete button on each device
- **Shows confirmation** dialog before deleting
- **Sends DELETE request** to `{API_BASE}/devices/{id}`
- **After success**: Updates local array and re-renders list
- **Error handling**: Shows alert on failure

## Backend Endpoints Required

You need to implement these endpoints in your backend:

### POST /devices
**Request**: Device registration data
**Response**: 
```json
{
  "status": "success",
  "device_id": "sensor-1"
}
```

### GET /devices
**Request**: None
**Response**: 
```json
{
  "devices": [
    {
      "id": "sensor-1",
      "friendly_name": "Living Room Sensor",
      "location": "North Wall",
      "telemetry_topic": "home/sensors/sensor-1",
      "command_topic": "home/commands/sensor-1"
    }
  ]
}
```

### DELETE /devices/{id}
**Request**: None
**Response**: 
```json
{
  "status": "success"
}
```

## Global Variables

- `registeredDevices` - Array storing fetched devices list

## Event Flow

1. User clicks **Sensors** in sidebar
2. `loadView(sensorsTemplate)` is called
3. `fetchAndRenderDevices()` fetches devices from cloud
4. Devices list is rendered in Card 2
5. User fills form and clicks **Register Device**
6. `registerDevice()` auto-generates MQTT topics
7. POST request sent to `/devices` endpoint
8. Device is saved to cloud database
9. Devices list is refreshed automatically
10. User can click **Delete** to remove a device
11. DELETE request removes device from cloud

## Notes

- Auto-generates MQTT topics automatically (no user input needed)
- All device IDs must be unique
- Empty devices list shows helpful message
- Responsive design works on mobile/tablet screens
- Form resets after successful registration
- Delete action has confirmation dialog to prevent accidents
