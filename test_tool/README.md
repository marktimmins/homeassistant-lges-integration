# LGES API Debug Tool

A simple browser-based tool for testing the LG Energy Solutions API endpoints.

## Usage

1. Open `index.html` in your web browser
2. Enter your LG RESU Home Monitor credentials
3. Click **Login to LGES**
4. Use the API buttons to fetch data

## Features

- **Rate Limit Aware**: Responses are displayed immediately - only make requests when needed
- **Syntax Highlighting**: JSON responses are color-coded for easy reading
- **Copy to Clipboard**: One-click copy for sharing responses
- **Request Log**: Track all API calls made
- **No Server Required**: Runs entirely in your browser

## Security Notes

- Your credentials are only used locally in your browser
- No data is sent to any third-party servers
- Tokens are only stored in browser memory (cleared on refresh)
- Add this folder to `.gitignore` to avoid committing credentials
