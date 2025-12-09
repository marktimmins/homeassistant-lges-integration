# LG Energy Solutions (LGES) Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

An unofficial Home Assistant integration for LG Energy Solutions (LGES) solar inverter systems. This integration connects to the LG RESU Home Monitor portal to provide real-time monitoring of your solar power system.

## Features

- 🔋 **Battery Monitoring** - State of charge with dynamic battery icons
- ☀️ **Solar Production** - Current power and daily/monthly/total generation
- 💰 **Income Tracking** - Daily and total income in your local currency
- 📊 **System Status** - Online/offline status and last update time
- 🔄 **Auto-refresh** - Data updates every 5 minutes

## Sensors

Based on the LG RESU Home Monitor API, the following sensors are available:

### Real-Time Power Flow

| Sensor          | Description                                 | Unit |
| --------------- | ------------------------------------------- | ---- |
| Solar Power     | Real-time solar PV output                   | W    |
| Battery Power   | Battery charging/discharging power          | W    |
| Home Load Power | Current home consumption                    | W    |
| Grid Power      | Grid import (positive) or export (negative) | W    |

### Daily Energy (Today)

| Sensor                  | Description                   | Unit |
| ----------------------- | ----------------------------- | ---- |
| Generated Today         | Energy generated today        | kWh  |
| Grid Import Today       | Energy bought from grid today | kWh  |
| Grid Export Today       | Energy sold to grid today     | kWh  |
| Self Use Today          | Self-consumed solar today     | kWh  |
| Home Consumption Today  | Total home consumption today  | kWh  |
| Battery Charge Today    | Battery charged today         | kWh  |
| Battery Discharge Today | Battery discharged today      | kWh  |

### Monthly Energy (This Month)

| Sensor                       | Description                        | Unit |
| ---------------------------- | ---------------------------------- | ---- |
| Generated This Month         | Energy generated this month        | kWh  |
| Grid Import This Month       | Energy bought from grid this month | kWh  |
| Grid Export This Month       | Energy sold to grid this month     | kWh  |
| Self Use This Month          | Self-consumed solar this month     | kWh  |
| Home Consumption This Month  | Home consumption this month        | kWh  |
| Battery Charge This Month    | Battery charged this month         | kWh  |
| Battery Discharge This Month | Battery discharged this month      | kWh  |

### Yearly Energy (This Year)

| Sensor                      | Description                       | Unit |
| --------------------------- | --------------------------------- | ---- |
| Generated This Year         | Energy generated this year        | kWh  |
| Grid Import This Year       | Energy bought from grid this year | kWh  |
| Grid Export This Year       | Energy sold to grid this year     | kWh  |
| Self Use This Year          | Self-consumed solar this year     | kWh  |
| Home Consumption This Year  | Home consumption this year        | kWh  |
| Battery Charge This Year    | Battery charged this year         | kWh  |
| Battery Discharge This Year | Battery discharged this year      | kWh  |

### All-Time Energy

| Sensor                     | Description                      | Unit |
| -------------------------- | -------------------------------- | ---- |
| Generated All Time         | Lifetime energy generated        | kWh  |
| Grid Import All Time       | Lifetime energy bought from grid | kWh  |
| Grid Export All Time       | Lifetime energy sold to grid     | kWh  |
| Self Use All Time          | Lifetime self-consumed solar     | kWh  |
| Home Consumption All Time  | Lifetime home consumption        | kWh  |
| Battery Charge All Time    | Lifetime battery charged         | kWh  |
| Battery Discharge All Time | Lifetime battery discharged      | kWh  |

### Battery

| Sensor                     | Description               | Unit |
| -------------------------- | ------------------------- | ---- |
| Battery State of Charge    | Current battery level     | %    |
| Battery Capacity           | Total battery capacity    | kWh  |
| Battery Unit (per battery) | Individual battery status | %    |

### System Info

| Sensor         | Description                    | Unit      |
| -------------- | ------------------------------ | --------- |
| Status         | System status (Online/Offline) | -         |
| Solar Capacity | Installed solar panel capacity | kW        |
| Last Update    | Last data update from inverter | timestamp |

### Income

| Sensor       | Description            | Unit     |
| ------------ | ---------------------- | -------- |
| Daily Income | Income generated today | Currency |
| Total Income | Lifetime income        | Currency |

## Installation

### HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed
2. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations → ⋮ (menu) → Custom repositories
   - Add: `https://github.com/marktimmins/homeassistant-lges-integration`
   - Category: Integration
3. Search for "LG Energy Solutions" in HACS and install
4. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/lges_energy` folder from this repository
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "LG Energy Solutions"
4. Enter your LG RESU Home Monitor credentials:
   - **Email Address**: Your login email for lgresuhomemonitor.com
   - **Password**: Your password

The integration will automatically discover all power stations associated with your account.

## Usage

After setup, you'll find sensors for each power station in your Home Assistant. They can be used in:

- **Energy Dashboard** - Add generation sensors for solar tracking
- **Automations** - Trigger based on battery level or power thresholds
- **Cards** - Display real-time system status

### Example Automation

```yaml
automation:
  - alias: "Low Battery Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.lges_battery_state_of_charge
        below: 20
    action:
      - service: notify.mobile_app
        data:
          message: "Battery is low ({{ states('sensor.lges_battery_state_of_charge') }}%)"
```

### Example Dashboard Card

```yaml
type: entities
title: Solar System
entities:
  - entity: sensor.lges_current_power
  - entity: sensor.lges_battery_state_of_charge
  - entity: sensor.lges_daily_generation
  - entity: sensor.lges_status
```

## Debug Tool

A standalone web-based debug tool is included in the `test_tool/` folder. Open `test_tool/index.html` in your browser to:

- Test API authentication
- View raw API responses
- Help troubleshoot integration issues

## API Information

This integration uses the LG RESU Home Monitor API (SEMS Portal):

- **Portal**: lgresuhomemonitor.com / semsportal.com
- **API**: Regional endpoints (au.semsportal.com, etc.)
- **Polling Interval**: 5 minutes (to avoid rate limiting)

## Troubleshooting

### "Invalid username or password"

- Verify you can log in at [lgresuhomemonitor.com](https://www.lgresuhomemonitor.com)
- Ensure you're using the correct email and password

### "No power stations found"

- Your LG account may not have any registered inverters
- Contact your installer to verify your system is registered

### Sensors showing "Unknown"

- The inverter may be offline
- Check the "Status" sensor for current system state
- Check Home Assistant logs for API errors

## Disclaimer

This is an **unofficial** integration and is not affiliated with, endorsed by, or supported by LG Energy Solutions. Use at your own risk.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.
