#!/usr/bin/env python3
"""
PhoneRecon — FUTMinna Cybersecurity OSINT Tool
Combined offline (phonenumbers) + live API + Geolocation engine
Educational Purposes Only
"""

from flask import Flask, render_template, request, jsonify
import phonenumbers
from phonenumbers import carrier, geocoder, timezone as ph_timezone
import requests
from datetime import datetime
import pytz

app = Flask(__name__)

# ─────────────────────────────────────────────
#  LINE TYPE MAP
# ─────────────────────────────────────────────
LINE_TYPES = {
    0: "Fixed Line", 1: "Mobile", 2: "Fixed or Mobile",
    3: "Toll Free",  4: "Premium Rate", 5: "Shared Cost",
    6: "VOIP", 7: "Personal Number", 8: "Pager",
    9: "UAN", 10: "Voicemail", -1: "Unknown",
}

# ─────────────────────────────────────────────
#  OFFLINE ENGINE  (phonenumbers / libphonenumber)
# ─────────────────────────────────────────────
def offline_analysis(number: str) -> dict:
    try:
        parsed = phonenumbers.parse(number, None)
    except Exception as e:
        return {"error": f"Parse failed: {str(e)}"}

    if not phonenumbers.is_possible_number(parsed):
        return {"error": "Number is not a possible phone number."}

    line_type_id = phonenumbers.number_type(parsed)
    carrier_name = carrier.name_for_number(parsed, "en")
    country_name = geocoder.description_for_number(parsed, "en")
    # Try city-level first, fall back to country
    city_name    = geocoder.description_for_number(parsed, "en") or ""
    timezones    = list(ph_timezone.time_zones_for_number(parsed))
    region_code  = phonenumbers.region_code_for_number(parsed)

    return {
        "valid":         phonenumbers.is_valid_number(parsed),
        "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        "national":      phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
        "e164":          phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
        "country_code":  f"+{parsed.country_code}",
        "country":       country_name or "Unknown",
        "city":          city_name,
        "region":        region_code or "Unknown",
        "carrier":       carrier_name or "Unknown / Not in DB",
        "timezones":     timezones,
        "line_type":     LINE_TYPES.get(line_type_id, "Unknown"),
        "is_mobile":     line_type_id in (1, 2),
    }

# ─────────────────────────────────────────────
#  LIVE ENGINE  (AbstractAPI)
# ─────────────────────────────────────────────
def live_analysis(number: str, api_key: str) -> dict:
    if not api_key:
        return {"error": "No API key provided."}
    try:
        resp = requests.get(
            "https://phonevalidation.abstractapi.com/v1/",
            params={"api_key": api_key, "phone": number}, timeout=8
        )
        if resp.status_code == 401: return {"error": "Invalid AbstractAPI key."}
        if resp.status_code == 429: return {"error": "Rate limit reached (250/month free tier)."}
        if not resp.ok: return {"error": f"AbstractAPI HTTP {resp.status_code}"}
        d = resp.json()
        return {
            "valid":        d.get("valid", False),
            "local_format": d.get("local_format", ""),
            "country_name": d.get("country", {}).get("name", ""),
            "country_code": d.get("country", {}).get("calling_code", ""),
            "country_iso":  d.get("country", {}).get("code", ""),
            "carrier":      d.get("carrier", ""),
            "line_type":    d.get("type", ""),
            "location":     d.get("location", ""),
        }
    except requests.exceptions.Timeout:
        return {"error": "AbstractAPI timed out."}
    except Exception as e:
        return {"error": str(e)}

# ─────────────────────────────────────────────
#  GEOLOCATION ENGINE  (OpenCage)
# ─────────────────────────────────────────────
def get_geolocation(query: str, opencage_key: str) -> dict:
    """
    Query OpenCage for coordinates + enriched location data.
    Falls back to ip-api.com country-level if no key provided.
    """
    if not query or query in ("Unknown", "—"):
        return {}

    # ── With OpenCage key ──
    if opencage_key:
        try:
            resp = requests.get(
                "https://api.opencagedata.com/geocode/v1/json",
                params={"q": query, "key": opencage_key, "limit": 1, "no_annotations": 0},
                timeout=8
            )
            if resp.status_code == 401:
                return {"error": "Invalid OpenCage key."}
            if resp.status_code == 429:
                return {"error": "OpenCage rate limit reached."}
            data = resp.json()
            if not data.get("results"):
                return {"error": "No geolocation results found."}
            r   = data["results"][0]
            geo = r.get("geometry", {})
            comp = r.get("components", {})
            ann  = r.get("annotations", {})
            return {
                "lat":          geo.get("lat"),
                "lng":          geo.get("lng"),
                "formatted":    r.get("formatted", ""),
                "country":      comp.get("country", ""),
                "state":        comp.get("state", ""),
                "city":         comp.get("city") or comp.get("town") or comp.get("village", ""),
                "continent":    comp.get("continent", ""),
                "currency":     ann.get("currency", {}).get("name", ""),
                "currency_sym": ann.get("currency", {}).get("symbol", ""),
                "calling_code": ann.get("callingcode", ""),
                "flag":         ann.get("flag", ""),
                "osm_url":      ann.get("OSM", {}).get("url", ""),
                "source":       "OpenCage",
            }
        except requests.exceptions.Timeout:
            return {"error": "OpenCage timed out."}
        except Exception as e:
            return {"error": str(e)}

    # ── Without key: use free restcountries for country-level only ──
    try:
        # Extract ISO code from query if it's a 2-letter code
        country_query = query.strip()
        resp = requests.get(
            f"https://restcountries.com/v3.1/name/{requests.utils.quote(country_query)}",
            timeout=6
        )
        if resp.ok:
            data = resp.json()
            if data:
                c = data[0]
                latlng = c.get("latlng", [None, None])
                capital = c.get("capital", [""])[0] if c.get("capital") else ""
                currencies = c.get("currencies", {})
                cur_name = ""
                cur_sym  = ""
                if currencies:
                    first = next(iter(currencies.values()))
                    cur_name = first.get("name", "")
                    cur_sym  = first.get("symbol", "")
                return {
                    "lat":          latlng[0] if len(latlng) > 0 else None,
                    "lng":          latlng[1] if len(latlng) > 1 else None,
                    "formatted":    c.get("name", {}).get("common", country_query),
                    "country":      c.get("name", {}).get("common", ""),
                    "state":        "",
                    "city":         capital,
                    "continent":    c.get("region", ""),
                    "currency":     cur_name,
                    "currency_sym": cur_sym,
                    "calling_code": "",
                    "flag":         c.get("flag", ""),
                    "osm_url":      "",
                    "source":       "restcountries.com (no key)",
                }
    except Exception:
        pass

    return {}

# ─────────────────────────────────────────────
#  LOCAL TIME ENGINE
# ─────────────────────────────────────────────
def get_local_times(timezones: list) -> list:
    """Return current local time for each timezone."""
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    results = []
    for tz_name in timezones:
        try:
            tz  = pytz.timezone(tz_name)
            local = now_utc.astimezone(tz)
            results.append({
                "tz":    tz_name,
                "time":  local.strftime("%H:%M"),
                "date":  local.strftime("%a, %d %b %Y"),
                "offset": local.strftime("%z"),
            })
        except Exception:
            results.append({"tz": tz_name, "time": "—", "date": "—", "offset": ""})
    return results

# ─────────────────────────────────────────────
#  OSINT LINKS
# ─────────────────────────────────────────────
def generate_osint_links(number: str, country: str) -> list:
    clean   = number.replace("+", "").replace(" ", "").replace("-", "")
    encoded = requests.utils.quote(number)
    links = [
        {"platform": "Google — Exact",  "url": f"https://www.google.com/search?q=%22{encoded}%22",  "icon": "🔍"},
        {"platform": "Google — Digits", "url": f"https://www.google.com/search?q=%22{clean}%22",    "icon": "🔍"},
        {"platform": "Truecaller",      "url": f"https://www.truecaller.com/search/{clean}",         "icon": "📋"},
        {"platform": "WhatsApp",        "url": f"https://wa.me/{clean}",                             "icon": "💬"},
        {"platform": "Sync.me",         "url": f"https://sync.me/search/?number={encoded}",         "icon": "🔗"},
        {"platform": "NumLookup",       "url": f"https://www.numlookup.com/?q={clean}",              "icon": "📡"},
    ]
    if country and "nigeria" in country.lower():
        links.append({"platform": "Nairaland", "url": f"https://www.nairaland.com/search?q={clean}", "icon": "🇳🇬"})
    return links

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/lookup", methods=["POST"])
def lookup():
    data         = request.get_json()
    number       = (data.get("phone", "")        or "").strip()
    abstract_key = (data.get("api_key", "")      or "").strip()
    opencage_key = (data.get("opencage_key", "") or "").strip()

    if not number:
        return jsonify({"error": "No phone number provided."}), 400

    # 1. Offline
    offline = offline_analysis(number)
    if "error" in offline:
        return jsonify({"error": offline["error"]}), 400

    # 2. Live (AbstractAPI)
    live = {}
    if abstract_key:
        live = live_analysis(number, abstract_key)

    # 3. Merge identity fields
    carrier_final   = live.get("carrier")   or offline.get("carrier")   or "—"
    line_type_final = live.get("line_type") or offline.get("line_type") or "—"
    country_final   = live.get("country_name") or offline.get("country") or "—"
    location_final  = live.get("location")  or offline.get("city")      or country_final
    carrier_source  = "live (AbstractAPI)" if (abstract_key and not live.get("error") and live.get("carrier")) \
                      else "offline (libphonenumber DB)"

    # 4. Geolocation — use most specific query available
    geo_query = location_final if location_final not in ("—", "") else country_final
    geo = get_geolocation(geo_query, opencage_key)

    # 5. Local time
    local_times = get_local_times(offline.get("timezones", []))

    # 6. OSINT links
    osint_links = generate_osint_links(number, country_final)

    result = {
        "timestamp":      datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "queried_number": number,
        "valid":          offline["valid"],
        "live_valid":     live.get("valid") if abstract_key and not live.get("error") else None,
        "international":  offline["international"],
        "national":       offline["national"],
        "e164":           offline["e164"],
        "local_format":   live.get("local_format", ""),
        "country":        country_final,
        "country_iso":    live.get("country_iso") or offline.get("region"),
        "country_code":   offline["country_code"],
        "location":       location_final,
        "carrier":        carrier_final,
        "carrier_source": carrier_source,
        "line_type":      line_type_final,
        "is_mobile":      offline["is_mobile"],
        "timezones":      offline["timezones"],
        "local_times":    local_times,
        "geo":            geo,
        "live_error":     live.get("error") if abstract_key else None,
        "osint_links":    osint_links,
    }
    return jsonify(result)

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════╗
║   PhoneRecon — FUTMinna OSINT Tool       ║
║   Open http://127.0.0.1:5000             ║
╚══════════════════════════════════════════╝
""")
    app.run(debug=True, port=5000)
