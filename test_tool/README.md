# LGES API Debug Tool

A single web page that shows what the Solarportal+ (SEMS+) API returns for your account, without Home Assistant. It's useful when a sensor looks wrong and you want to see the data behind it.

## How to use it

1. Open `index.html` in your web browser. Double-clicking the file is fine; there's nothing to install.
2. Enter the email and password you use at [au.solarportalplus.com](https://au.solarportalplus.com) and click **Log in**. Your systems load automatically.
3. Choose your system (if you have more than one) and click **Fetch Everything**.

The page has two tabs:

- **Sensors** shows every sensor the Home Assistant integration creates, with the same names: live power, solar strings, battery, today's self-consumption, income, system status, inverter readings, an energy table (today, this month, this year, all time) and recent alarms. Hover over any text that's cut off with "…" to see it in full.
  - **—** means that request hasn't been run yet.
  - **not reported** means the API didn't return that value for your system. Home Assistant will show it as Unknown.
- **Raw responses** lists every API response, newest first. Click one to expand the JSON, or use **Copy** to copy it.

You can also run requests one at a time. They're grouped into **Live data** (power flow and status, inverter readings, alarms), **System** (station details with the battery and solar capacities, devices and batteries), **Energy totals** (today, this month, this year, all time) and **Income**.

## Keep your login safe

- Your email and password are only sent to the Solarportal+ and GoodWe SEMS+ login servers, straight from your browser. Nothing goes anywhere else.
- Your session is kept in memory only and disappears when you close or refresh the page. The login response shown on the page has the session token hidden.
- Responses include your address, email and device serial numbers. Remove those before posting them in an issue, or sharing a saved copy or screenshot of the page.
