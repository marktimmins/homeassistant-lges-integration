# LG Energy Solutions (LGES) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

An unofficial Home Assistant integration for LG Energy Solutions solar and battery systems (LG ESS / RESU). It reads the same data you see in the Solarportal+ monitoring portal and turns it into Home Assistant sensors: live solar, battery, grid and home power; daily, monthly, yearly and lifetime energy; income; system status; and alarms.

> **You need version 2.0.0 or later from September 2026 onwards.** LG's monitoring provider, GoodWe, switched off the old LG RESU Home Monitor API and moved everyone to **Solarportal+** (SEMS+). Older versions of this integration stopped getting data. Update to 2.0.0. Your login and sensors stay the same.

## Contents

- [Compatibility](#compatibility)
- [Before you start](#before-you-start)
- [Install](#install)
- [Set up](#set-up)
- [Updating from version 1.x](#updating-from-version-1x)
- [Use it in the Energy dashboard](#use-it-in-the-energy-dashboard)
- [Sensors](#sensors)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Debug tool](#debug-tool)
- [How it works](#how-it-works)

## Compatibility

This integration is built and tested for **LG Energy Solutions** home battery systems (LG ESS / RESU) monitored through **Solarportal+** ([au.solarportalplus.com](https://au.solarportalplus.com)).

Solarportal+ isn't run by LG. It's an unbranded edition of GoodWe's **SEMS+** monitoring platform, runs on GoodWe's servers, and its app is published by Azure Solar Co., Ltd. Because the integration talks to SEMS+ rather than to anything LG-specific, it may also work with other brands monitored through Solarportal+ or GoodWe's own SEMS+ portal, such as GoodWe inverters. **Other brands have not been tested.** Some sensors may be missing or show unexpected values. Sign in with the email and password you use for your Solarportal+ or SEMS+ app or portal.

If you try it with another brand, please [open an issue](https://github.com/marktimmins/homeassistant-lges-integration/issues) and say how it went, including your inverter and battery models. Confirmed systems will be listed here.

## Before you start

You need:

1. **Home Assistant** 2024.1 or newer.
2. **A Solarportal+ login that works.** Check you can sign in at [au.solarportalplus.com](https://au.solarportalplus.com) with your email and password. This is the same account you used for LG RESU Home Monitor. If you can't sign in there, the integration won't be able to either.
3. **Two-factor sign-in turned off** for that account. The integration can't enter verification codes.

## Install

### Option 1: HACS (recommended)

[HACS](https://hacs.xyz/) is the Home Assistant Community Store. It installs custom integrations and tells you when updates are available. If you don't have it yet, follow the [HACS install guide](https://hacs.xyz/docs/use/) first.

1. In Home Assistant, open **HACS** from the sidebar.
2. Click the **⋮** menu (top right) and choose **Custom repositories**.
3. Paste `https://github.com/marktimmins/homeassistant-lges-integration` into **Repository**, choose **Integration** as the type, and click **Add**.
4. Search HACS for **LG Energy Solutions**, open it, and click **Download**.
5. Restart Home Assistant: **Settings** → **System** → power icon (top right) → **Restart Home Assistant**.

### Option 2: Manual

1. Download this repository as a ZIP (the green **Code** button → **Download ZIP**) and unzip it.
2. Copy the `custom_components/lges_energy` folder into your Home Assistant `config/custom_components/` folder. Create `custom_components` if it doesn't exist. You should end up with `config/custom_components/lges_energy/manifest.json`.
3. Restart Home Assistant.

## Set up

1. Go to **Settings** → **Devices & services**.
2. Click **+ Add integration** (bottom right) and search for **LG Energy Solutions**.
3. Enter the email and password you use at [au.solarportalplus.com](https://au.solarportalplus.com) and click **Submit**.

That's it. The integration finds every system on your account and adds a device for each one, named after its address. Sensors update every 5 minutes. To see them, open **Settings** → **Devices & services** → **LG Energy Solutions** and click your device.

## Updating from version 1.x

1. Update the integration in HACS (or copy the new files in manually) and restart Home Assistant.
2. There's nothing else to do: your login, sensors and their history carry over.

What changed in 2.0:

- **New sensors:** `Self-Consumption Today`, `Self-Sufficiency Today`, `Active Alarms`, `Inverter Temperature`, `Grid Voltage`, `Backup Power`, `Inverter Rated Power`, `Export Income Today`, and power and voltage sensors for each solar panel string.
- **Battery Capacity** now comes from your system's settings (the portal's **Basic Information** page). It shows Unknown if no battery capacity has been entered there.
- **Renamed attribute:** the per-battery sensors' `local` attribute is now `connected`.
- **Status** now shows `Waiting` when the inverter is on standby, for example at night.
- **Device model:** the device page now shows your inverter model.
- **Icon:** the integration now has its own icon in **Devices & services** (Home Assistant 2026.3 or newer).

## Use it in the Energy dashboard

Go to **Settings** → **Dashboards** → **Energy** and add:

| Energy dashboard setting       | Sensor to choose          |
| ------------------------------ | ------------------------- |
| Solar production               | `Generated Today`         |
| Grid consumption               | `Grid Import Today`       |
| Return to grid                 | `Grid Export Today`       |
| Home battery: energy going in  | `Battery Charge Today`    |
| Home battery: energy coming out | `Battery Discharge Today` |

These sensors reset to zero at midnight. Home Assistant handles that automatically. The Energy dashboard only shows data from the day you add the sensors onwards.

## Sensors

Each system gets the sensors below. Some systems don't report every value, for example battery power on some inverters. Those sensors show **Unknown**.

### Live power (updates every 5 minutes)

| Sensor          | What it shows                                                  | Unit |
| --------------- | -------------------------------------------------------------- | ---- |
| Solar Power     | Solar panel output right now                                   | W    |
| Battery Power   | Battery power: positive = discharging, negative = charging     | W    |
| Home Load Power | What your home is using right now                              | W    |
| Grid Power      | Grid power: positive = buying (import), negative = selling (export) | W    |

### Energy today

| Sensor                  | What it shows                                                        | Unit |
| ----------------------- | -------------------------------------------------------------------- | ---- |
| Generated Today         | Solar energy generated today                                         | kWh  |
| Grid Import Today       | Energy bought from the grid today                                    | kWh  |
| Grid Export Today       | Energy sold to the grid today                                        | kWh  |
| Self Use Today          | Solar energy used at home (directly or via the battery) today        | kWh  |
| Home Consumption Today  | Total energy your home used today                                    | kWh  |
| Battery Charge Today    | Energy put into the battery today                                    | kWh  |
| Battery Discharge Today | Energy taken out of the battery today                                | kWh  |
| Self-Consumption Today  | Share of today's solar used at home rather than exported (new in 2.0) | %    |
| Self-Sufficiency Today  | Share of today's home use covered by solar and battery (new in 2.0) | %    |

### Energy this month, this year and all time

The same seven energy sensors are also available as **This Month**, **This Year** and **All Time** versions, for example `Generated This Month`, `Grid Import This Year` and `Battery Charge All Time`. All-time totals cover everything since your system was installed.

### Battery

| Sensor                  | What it shows                                                  | Unit |
| ----------------------- | -------------------------------------------------------------- | ---- |
| Battery State of Charge | How full the battery is                                        | %    |
| Battery Capacity        | Battery size, as entered in the portal's Basic Information page | kWh  |
| Battery *n*             | One per battery the system reports. Its `connected` attribute shows whether the inverter can see it | %    |

### Inverter (new in 2.0)

| Sensor               | What it shows                                                                 | Unit |
| -------------------- | ----------------------------------------------------------------------------- | ---- |
| Inverter Temperature | Temperature inside the inverter                                               | °C   |
| Grid Voltage         | Mains voltage at the inverter. Useful for spotting high-voltage cut-outs      | V    |
| Backup Power         | Power going to backed-up (essential) circuits. 0 if you don't have any        | W    |
| Inverter Rated Power | The inverter's maximum output, from your system's settings                   | kW   |

Inverter Temperature, Grid Voltage and Backup Power come from the inverter's live readings (the first inverter, if you have more than one). If the monitoring servers don't allow that request for your account, those three show **Unknown** and everything else keeps working.

### Solar strings (new in 2.0)

Most inverters have two or more inputs (MPPT trackers), each with its own string of solar panels. You get two sensors per string, for example `Solar String 1 Power` (W) and `Solar String 1 Voltage` (V). Comparing strings on a sunny day helps spot shading or a faulty panel. A string with fewer panels runs at a lower voltage, so different strings don't need to match.

The string sensors are created when the integration starts. If the inverter readings weren't available then, they appear after the next Home Assistant restart.

### System

| Sensor         | What it shows                                                                                       | Unit      |
| -------------- | --------------------------------------------------------------------------------------------------- | --------- |
| Status         | `Online` (running), `Waiting` (standby, normal at night), `Offline`, or `Error`                      | -         |
| Active Alarms  | How many inverter or battery alarms are happening right now (new in 2.0). See below. | count     |
| Solar Capacity | Size of your solar panel system, from your system's settings                                        | kW        |
| Last Update    | When the inverter last sent data                                                                    | timestamp |

**Active Alarms** is `0` when everything is fine. Its attributes list each active alarm (name, device, level and start time), plus the most recent alarm from the last 90 days, even if it has cleared. These are the same alarms shown in the portal's **Alarms** page. It's a quick way to spot problems such as a battery that has stopped working.

### Income

| Sensor       | What it shows                                    | Unit                 |
| ------------ | ------------------------------------------------ | -------------------- |
| Daily Income | Value of today's solar generation                | Your currency, e.g. AUD |
| Export Income Today | The part of today's income from solar sold to the grid | Your currency |
| Total Income | Lifetime value, adding up each year since install | Your currency        |

Income uses the electricity price set in the portal. If it looks wrong, check the price settings at [au.solarportalplus.com](https://au.solarportalplus.com). If Total Income stays **Unknown**, the portal didn't return yearly income for your account. The integration tries again every 6 hours.

## Examples

Your sensor entity IDs start with your system's name, which is usually its address. Find them on the device page (**Settings** → **Devices & services** → **LG Energy Solutions** → your device). Then replace `sensor.my_home_...` below with your own IDs.

### Get a phone notification when an alarm starts

```yaml
alias: "Solar alarm"
trigger:
  - platform: numeric_state
    entity_id: sensor.my_home_active_alarms
    above: 0
action:
  - service: notify.notify
    data:
      title: "Solar system alarm"
      message: >
        {{ state_attr('sensor.my_home_active_alarms', 'active_alarms')
           | map(attribute='name') | join(', ') }}
```

### Warn when the battery is low

```yaml
alias: "Low battery"
trigger:
  - platform: numeric_state
    entity_id: sensor.my_home_battery_state_of_charge
    below: 20
action:
  - service: notify.notify
    data:
      message: "Battery is at {{ states('sensor.my_home_battery_state_of_charge') }}%"
```

### Dashboard card

```yaml
type: entities
title: Solar system
entities:
  - sensor.my_home_solar_power
  - sensor.my_home_battery_state_of_charge
  - sensor.my_home_grid_power
  - sensor.my_home_generated_today
  - sensor.my_home_status
  - sensor.my_home_active_alarms
```

## Troubleshooting

### "Invalid username or password"

- Check you can sign in at [au.solarportalplus.com](https://au.solarportalplus.com) with the same email and password.
- Make sure two-factor sign-in is turned off for the account.

### Home Assistant asks you to sign in again

If your password changes (or two-factor sign-in gets turned on), the integration stops updating and **Settings** → **Devices & services** shows LG Energy Solutions as needing attention. Click **Reconfigure**, enter your current password, and it picks up where it left off. It doesn't keep retrying the old password, so your LG account won't get locked.

### "Failed to connect"

- Check Home Assistant has internet access, then try again in a few minutes. The Solarportal+ (GoodWe) servers are sometimes briefly unavailable.

### "No power stations found"

- Your account has no systems linked to it. Ask your installer to add your system to your account.

### Some sensors show "Unknown"

- Check whether the portal shows the same value. If the portal doesn't have it, your system isn't reporting it. For example, some inverters don't send battery power or battery level.
- If the battery sensors were working and then stopped, check **Active Alarms** and the battery itself. A battery that is switched off or has tripped will stop reporting.

### Turn on debug logging

If you need to report a problem, add this to `configuration.yaml`, restart, and check **Settings** → **System** → **Logs**:

```yaml
logger:
  default: warning
  logs:
    custom_components.lges_energy: debug
```

Debug logs include the data returned by the API, which includes your address and email. Remove anything personal before sharing logs in an issue.

## Debug tool

The `test_tool/` folder has a small web page that shows what the API returns for your account, without Home Assistant. Open `test_tool/index.html` in your browser, log in, and click **Fetch Everything**. The **Sensors** tab shows every Home Assistant sensor with its current value. The **Raw responses** tab shows the JSON behind them. See [test_tool/README.md](test_tool/README.md) for details.

## How it works

- **Login:** `au.solarportalplus.com` (Solarportal+), falling back to GoodWe's `semsplus.goodwe.com`. The login returns a regional data server (for example `au-gateway.semsportal.com`) that all other requests go to.
- **Data:**
  - `stations/flow`: live power
  - `stations/{id}`: system settings (battery capacity, solar capacity, rated power), checked once an hour
  - `stations/statistics`: energy totals and the self-consumption figures
  - `stations/production`: income
  - `equipments/{serial}/telemetry`: inverter temperature, grid voltage, backup power and solar strings
  - `stations/device/all-status` and `relatedDevices`: devices and batteries
  - `sems-alarm` alarm list: alarms
- **Polling:** every 5 minutes. Device lists and past years' totals are cached so each update makes only a handful of requests.
- **Lifetime totals:** Solarportal+ has no single lifetime figure, so the integration adds up each year since your system was installed.

## Disclaimer

This is an **unofficial** integration. It is not affiliated with, endorsed by, or supported by LG Energy Solutions or GoodWe. Use at your own risk.

## Contributing

Contributions are welcome. Fork the repository, create a feature branch, and open a pull request.

## License

MIT License. See the [LICENSE](LICENSE) file for details.
