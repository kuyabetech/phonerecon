# PhoneRecon — FUTMinna OSINT Tool
**Educational Purposes Only | Cybersecurity Coursework**

A combined offline + live phone number intelligence tool built with Flask.

---

## Features
- ✅ Offline validation using Google's libphonenumber (no API key needed)
- ⚡ Live carrier + validity via AbstractAPI (free, optional)
- 🗺️ Country, region, carrier, line type, timezones
- 🔍 One-click OSINT links (Google, Truecaller, WhatsApp, Sync.me, NumLookup)
- 🇳🇬 Nigerian-specific: Nairaland link added automatically for NG numbers

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. (Optional) Get a free AbstractAPI key
- Go to https://abstractapi.com/api/phone-validation
- Sign up → copy your free API key
- Paste it in the web UI when running (250 lookups/month free)

### 3. Run the server
```bash
python app.py
```

### 4. Open your browser
```
http://127.0.0.1:5000
```

---

## How it works

| Layer | Library | Requires Key? | Data Type |
|-------|---------|---------------|-----------|
| Offline | `phonenumbers` (libphonenumber) | No | Static DB — carrier/country |
| Live | AbstractAPI Phone Validation | Yes (free) | Real-time — portable numbers |

**Why two layers?**
The `phonenumbers` library uses a static database compiled by Google. It is great for format validation and broad carrier identification, but does NOT reflect number portability (e.g., a number ported from MTN to Airtel will still show MTN). The live AbstractAPI layer queries real-time data to fix this gap.

---

## Legal Notice
- Only query numbers you own or have explicit written permission to investigate
- Unauthorized OSINT on third-party numbers may violate the **Nigerian Cybercrimes Act 2015**
- This tool does not store or log any phone numbers
# phonerecon
# phonerecon
