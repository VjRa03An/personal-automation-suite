# ⬡ GasFind — On-Demand Gas Price Tracker PWA

A mobile-first Progressive Web App (PWA) that finds the cheapest gas stations near you or across San Jose, CA — on demand, PIN-secured, and installable to your home screen.

---

## Features

- **📍 Near Me mode** — Uses your device GPS to find cheap gas within a radius you choose (2, 5, 10, 15, 25, or 50 miles). Great for road trips.
- **🏙 San Jose, CA mode** — Searches all zip codes across San Jose (95110–95136) or a specific area/zip you enter.
- **🔒 PIN security** — 4-digit PIN lock screen on every open. Auto-locks after 5 minutes of inactivity with a live countdown bar.
- **⚡ On-demand** — No background jobs, no cron. Tap the button, get live prices.
- **📲 Installable** — Full PWA with manifest + service worker. Add to home screen on iOS or Android.
- **🌐 AI-powered** — Uses the Anthropic API with live web search to pull real, current prices.

---

## Screenshots

```
┌─────────────────────┐
│  ⬡ GasFind    🔒 Lock│
│ ─────────────────── │
│ [📍 Near me] [🏙 SJ] │
│                     │
│ 📍 Your location    │
│  123 Main St, SJ    │
│                     │
│ Fuel    Radius      │
│ [Reg▾] [5 miles▾]  │
│                     │
│  Find Gas Near Me → │
│                     │
│ $3.899  $4.012  12  │
│ Cheapest Avg  Chkd  │
│                     │
│ 1 ARCO · Cheapest ✓ │
│   $3.899/gal        │
│ 2 Shell · +$0.020   │
│   $3.919/gal        │
└─────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| App shell | Vanilla HTML/CSS/JS — zero dependencies |
| AI Agent | Anthropic API (`claude-sonnet-4-20250514`) |
| Live prices | Anthropic web search tool |
| Geolocation | Browser `navigator.geolocation` API |
| Reverse geocoding | OpenStreetMap Nominatim (free, no key needed) |
| Offline support | Service Worker + Cache API |
| Install | Web App Manifest (PWA) |
| Security | 4-digit PIN, hashed with djb2, stored in `localStorage` |

---

## Project Structure

```
gas-tracker-pwa/
├── index.html       # Main app — all UI, logic, and agent calls
├── manifest.json    # PWA manifest for home screen install
├── sw.js            # Service worker for offline caching
├── icon-192.svg     # App icon (192×192)
├── icon-512.svg     # App icon (512×512)
└── README.md        # This file
```

---

## Setup & Deployment

### Prerequisites

- An [Anthropic API key](https://console.anthropic.com/) with access to `claude-sonnet-4-20250514`
- A static hosting provider that supports **HTTPS** (required for PWA install + geolocation)

### 1. Add your API key

Open `index.html` and locate the fetch call to `https://api.anthropic.com/v1/messages`. The app expects the API key to be injected at the hosting/proxy layer — **never hardcode your API key in client-side code**.

For a quick personal deployment, use a small backend proxy or a service like Cloudflare Workers to attach the `x-api-key` header server-side.

> ⚠️ **Security note:** The Anthropic API key must never be exposed in client-side JavaScript. Always route API calls through a backend or proxy that holds the key in an environment variable.

### 2. Deploy the files

Upload all 5 files to your static host:

```bash
# Example: GitHub Pages via gh-pages branch
git init
git add .
git commit -m "Initial deploy"
git remote add origin https://github.com/YOUR_USERNAME/gas-tracker-pwa.git
git push -u origin main
```

Then enable GitHub Pages in your repo settings → Pages → Source: `main` branch.

### 3. Install on your phone

**iOS (Safari):**
1. Open your deployed URL in Safari
2. Tap the Share button (box with arrow)
3. Tap **Add to Home Screen**
4. Tap **Add**

**Android (Chrome):**
1. Open your deployed URL in Chrome
2. Tap the menu (⋮) → **Add to Home screen**
3. Tap **Add**

---

## Security Model

| Feature | Detail |
|---|---|
| PIN storage | Hashed with djb2 algorithm, stored in `localStorage` — plain PIN is never saved |
| Auto-lock | Resets on any touch/click/keypress. Locks after 5 min of true inactivity |
| Manual lock | Tap 🔒 Lock in the header at any time |
| PIN reset | Tap PIN button in header → confirm → set a new one |
| Data cleared on lock | Results are wiped from the screen when the app locks |
| API key | Must be kept server-side — never in this client code |

---

## Customization

| What | Where |
|---|---|
| Change lock timeout | `const LOCK_SEC = 300;` in `index.html` (seconds) |
| Change default city | Update city mode prompt strings from `San Jose, CA` to your city |
| Add more radius options | Add `<option>` tags to `#gpsRadius` select |
| Change accent color | Update `--accent: #c8f542;` CSS variable |

---

## API Usage Notes

- Each search triggers **one Anthropic API call** with the `web_search` tool enabled
- The model performs 1–3 web searches internally to gather prices, then returns structured JSON
- Average cost per search: ~$0.003–0.006 (Sonnet 4 pricing)
- No data is stored or logged by this app — each search is stateless

---

## License

MIT — free to use, modify, and deploy.

---

*Built with the Anthropic API. Prices are sourced live via web search and should always be verified at the pump.*
