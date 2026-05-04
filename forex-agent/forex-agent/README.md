# ForexWatch — USD → INR Daily Digest Agent

Sends you a daily email with the best USD→INR rate from 7 providers.
Runs automatically on GitHub Actions every morning. No app, no phone needed.

---

## Your settings
| Setting | Value |
|---------|-------|
| Delivery time | 8:00 AM IST (2:30 AM UTC) |
| Rate alert | Only sends if best rate is above ₹94 |
| Transfer amount | $1,000 (change in workflow file if needed) |
| Providers tracked | Wise · Remitly · Western Union · PayPal/Xoom · SBI Remit · JPMorgan Chase · Bank of America |

---

## What's in this repo

```
forexwatch/
├── .github/
│   └── workflows/
│       └── forex-digest.yml   ← the schedule & runner (GitHub Actions)
├── scripts/
│   └── send_digest.py         ← the agent (fetches rates, sends email)
├── logs/
│   └── .gitkeep               ← rate history saved here (ignored by git)
├── .gitignore
└── README.md
```

---

## One-time setup (do this once, then forget it)

### Step 1 — Gmail App Password

You need a special password just for this agent (not your normal Gmail password).

1. Go to **myaccount.google.com**
2. Click **Security → 2-Step Verification** (enable if not already on)
3. Scroll down → **App passwords**
4. App: Mail · Device: Other → type "ForexWatch" → **Generate**
5. Copy the 16-character password — you only see it once

### Step 2 — Add secrets to GitHub

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these four secrets:

| Secret name | What to paste |
|-------------|---------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `DIGEST_EMAIL` | Email address to receive the digest |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASS` | The 16-character App Password from Step 1 |

### Step 3 — Test it immediately

Don't wait until tomorrow morning.

1. GitHub repo → **Actions** tab
2. Click **ForexWatch Daily Digest** in the left list
3. Click **Run workflow → Run workflow** (green button)
4. Watch the steps complete (takes ~60 seconds)
5. Check your inbox — digest arrives within 2 minutes

A green tick = success. A red cross = click it and send the error to Claude.

---

## What the email looks like

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FOREXWATCH · USD → INR Daily Digest
  2026-05-04
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  BEST RATE TODAY
  ₹94.45 per $1 via Wise
  For $1,000 → ₹94,450

  ✅ Rate IS above your ₹94 threshold

  ALL PROVIDERS (best → lowest)
  ──────────────────────────────────────
  ★ Wise               ₹94.45   mid-market rate
    Remitly            ₹94.20   economy: no fee
    Western Union      ₹93.50   bank deposit
    PayPal / Xoom      ₹92.80   instant
    JPMorgan Chase     ₹80.96   wire, $45 fee
    Bank of America    ₹79.44   wire, $45 fee
  ──────────────────────────────────────

  AGENT INSIGHT
  Wise and Remitly offer rates within 1% of mid-market.
  Bank wires (JPMC/BofA) cost ₹13,000–₹15,000 more per
  $1,000 transferred, before the $45 wire fee.

  Sent by ForexWatch · Powered by Claude
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Changing settings

**Different transfer amount** — open `.github/workflows/forex-digest.yml`,
change `TRANSFER_AMOUNT: "1000"` to your amount.

**Different rate threshold** — same file, change `ALERT_THRESHOLD: "94"`.

**Different delivery time** — change the cron line.
Cron uses UTC. IST = UTC + 5:30.
- 7 AM IST = `'0 1 * * *'`
- 8 AM IST = `'30 2 * * *'` ← current
- 9 AM IST = `'30 3 * * *'`

**Pause the agent** — Actions tab → ForexWatch Daily Digest → ··· → Disable workflow.

---

## Security

- API key never touches the browser — stored only in GitHub Secrets
- Email credentials stored only in GitHub Secrets — never in code
- AI response validated before use (rate sanity check: ₹60–₹120 range)
- Email address validated before sending
- SMTP uses TLS 1.2+ with verified certificates
- Rate logs saved with owner-only file permissions

---

## Shared infrastructure

This agent reuses the same secrets as your other agents in this repo.
No new API keys or passwords needed for additional agents.

| Secret | Shared with |
|--------|-------------|
| `ANTHROPIC_API_KEY` | All Claude-powered agents |
| `SMTP_USER` / `SMTP_PASS` | All email digest agents |
| `DIGEST_EMAIL` | All digest agents (or set per-agent) |
