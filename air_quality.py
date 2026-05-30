import requests
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
CITY      = "New York"
DAYS_BACK = 30
API_KEY   = "your_api_key"
HEADERS   = {"X-API-Key": API_KEY, "Accept": "application/json"}
# ─────────────────────────────────────────────────────────────────────────────

CITY_COORDS = {
    "New York":     (40.7128, -74.0060),
    "Los Angeles":  (34.0522, -118.2437),
    "Chicago":      (41.8781, -87.6298),
    "Houston":      (29.7604, -95.3698),
    "Boston":       (42.3601, -71.0589),
    "Phoenix":      (33.4484, -112.0740),
    "Philadelphia": (39.9526, -75.1652),
    "Seattle":      (47.6062, -122.3321),
    "Denver":       (39.7392, -104.9903),
    "Miami":        (25.7617, -80.1918),
    "Atlanta":      (33.7490, -84.3880),
}


def get_locations():
    lat, lon = CITY_COORDS.get(CITY, (40.7128, -74.0060))
    r = requests.get(
        "https://api.openaq.org/v3/locations",
        headers=HEADERS,
        params={"coordinates": f"{lat},{lon}", "radius": 25000, "limit": 10},
        timeout=15,
    )
    locs = r.json().get("results", [])
    print(f"  Found {len(locs)} stations near {CITY}")
    return locs


def get_pm25_sensor(location_id):
    r = requests.get(
        f"https://api.openaq.org/v3/locations/{location_id}/sensors",
        headers=HEADERS, timeout=15,
    )
    for s in r.json().get("results", []):
        name = str(s.get("parameter", {}).get("name", "")).lower()
        pid  = s.get("parameter", {}).get("id")
        if name == "pm25" or pid == 2:
            return s["id"]
    return None


def get_measurements(sensor_id):
    date_from = (datetime.utcnow() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT00:00:00Z")
    date_to   = datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")

    for endpoint in [
        f"https://api.openaq.org/v3/sensors/{sensor_id}/measurements/hourly",
        f"https://api.openaq.org/v3/sensors/{sensor_id}/measurements",
    ]:
        try:
            r = requests.get(
                endpoint, headers=HEADERS,
                params={"date_from": date_from, "date_to": date_to, "limit": 1000},
                timeout=20,
            )
            results = r.json().get("results", [])
            if not results:
                continue

            records = []
            for item in results:
                try:
                    # --- value: force to float, skip bad ones ---
                    val = item.get("value")
                    if val is None:
                        val = item.get("avg")
                    if val is None:
                        continue
                    val = float(val)
                    if val <= 0:
                        continue

                    # --- datetime: always parse as UTC then strip tz ---
                    raw = None
                    period = item.get("period") or {}
                    dtf = period.get("datetimeFrom") or {}
                    raw = dtf.get("utc") or dtf.get("local")
                    if not raw:
                        dt_field = item.get("datetime") or {}
                        raw = dt_field.get("utc") or dt_field.get("local")
                    if not raw:
                        date_field = item.get("date") or {}
                        raw = date_field.get("utc") or date_field.get("local")
                    if not raw:
                        continue

                    # parse and strip timezone completely
                    dt = pd.Timestamp(raw)
                    if dt.tzinfo is not None:
                        dt = dt.tz_convert("UTC").tz_localize(None)

                    records.append({"datetime": dt, "value": val})
                except Exception:
                    continue

            if len(records) > 5:
                df = pd.DataFrame(records)
                df["datetime"] = pd.to_datetime(df["datetime"])
                df["value"]    = df["value"].astype(float)
                df = df.sort_values("datetime").reset_index(drop=True)
                return df

        except Exception as e:
            print(f"    error on endpoint: {e}")

    return None


def aqi_cat(val):
    """Return (category_string, hex_color) for a PM2.5 float value."""
    v = float(val)
    if v <= 12.0:    return "Good",                           "#00e400"
    elif v <= 35.4:  return "Moderate",                       "#ffff00"
    elif v <= 55.4:  return "Unhealthy for Sensitive Groups", "#ff7e00"
    elif v <= 150.4: return "Unhealthy",                      "#ff0000"
    elif v <= 250.4: return "Very Unhealthy",                 "#8f3f97"
    else:            return "Hazardous",                      "#7e0023"


def build_dashboard(df, station_name):
    # guarantee clean types before any plotting
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["value"]    = df["value"].astype(float)
    df = df.sort_values("datetime").reset_index(drop=True)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.patch.set_facecolor("#0f1117")
    for ax in axes.flat:
        ax.set_facecolor("#1a1d27")
        ax.tick_params(colors="#aaaaaa", labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333344")

    # ── Panel 1: daily trend ──────────────────────────────────────────────────
    ax1 = axes[0, 0]
    daily = df.set_index("datetime")["value"].resample("D").mean().dropna()
    ax1.plot(daily.index, daily.values, color="#4a9eff", linewidth=1.5, zorder=2)
    ax1.fill_between(daily.index, daily.values, alpha=0.15, color="#4a9eff")
    ax1.axhline(12.0,  color="#00e400", lw=0.8, ls="--", alpha=0.7, label="Good (12)")
    ax1.axhline(35.4,  color="#ffff00", lw=0.8, ls="--", alpha=0.7, label="Moderate (35.4)")
    ax1.set_title(f"PM2.5 Daily Average — {CITY}", color="white", fontsize=11, pad=8)
    ax1.set_ylabel("PM2.5 (µg/m³)", color="#aaaaaa", fontsize=9)
    ax1.legend(fontsize=7, facecolor="#1a1d27", labelcolor="white", framealpha=0.5)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)

    # ── Panel 2: hourly averages ──────────────────────────────────────────────
    ax2 = axes[0, 1]
    df["hour"] = df["datetime"].dt.hour
    hourly = df.groupby("hour")["value"].mean()
    bar_colors = [aqi_cat(v)[1] for v in hourly.values.tolist()]
    ax2.bar(hourly.index.tolist(), hourly.values.tolist(),
            color=bar_colors, width=0.8, edgecolor="none")
    ax2.set_title("Average PM2.5 by Hour of Day", color="white", fontsize=11, pad=8)
    ax2.set_xlabel("Hour (0 = midnight)", color="#aaaaaa", fontsize=9)
    ax2.set_ylabel("PM2.5 (µg/m³)", color="#aaaaaa", fontsize=9)
    ax2.set_xticks(range(0, 24, 3))

    # ── Panel 3: AQI pie ──────────────────────────────────────────────────────
    ax3 = axes[1, 0]
    cat_labels = [aqi_cat(v)[0] for v in df["value"].tolist()]
    # shorten long label so it fits on chart
    SHORT_LABELS = {
        "Good":                           "Good",
        "Moderate":                       "Moderate",
        "Unhealthy for Sensitive Groups": "Sensitive Groups",
        "Unhealthy":                      "Unhealthy",
        "Very Unhealthy":                 "Very Unhealthy",
        "Hazardous":                      "Hazardous",
    }
    cat_labels_short = [SHORT_LABELS.get(l, l) for l in cat_labels]
    cats = pd.Series(cat_labels_short).value_counts()
    CAT_COLORS = {
        "Good":                           "#00e400",
        "Moderate":                       "#ffff00",
        "Unhealthy for Sensitive Groups": "#ff7e00",
        "Unhealthy":                      "#ff0000",
        "Very Unhealthy":                 "#8f3f97",
        "Hazardous":                      "#7e0023",
    }
    pie_colors = [CAT_COLORS.get(c, "#aaaaaa") for c in cats.index.tolist()]
    wedges, texts, autotexts = ax3.pie(
        cats.values.tolist(), labels=cats.index.tolist(),
        colors=pie_colors, autopct="%1.0f%%", startangle=140,
        textprops={"color": "white", "fontsize": 8},
        pctdistance=0.75, labeldistance=1.15,
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_color("#111111")
    ax3.set_title("Time in Each AQI Category", color="white", fontsize=11, pad=8)

    # ── Panel 4: summary card ─────────────────────────────────────────────────
    ax4 = axes[1, 1]
    ax4.axis("off")
    vals      = df["value"].tolist()
    avg       = float(sum(vals) / len(vals))
    peak      = float(max(vals))
    peak_time = df.loc[df["value"].idxmax(), "datetime"].strftime("%b %d, %I%p")
    good_pct  = sum(1 for v in vals if v <= 12.0)  / len(vals) * 100
    bad_pct   = sum(1 for v in vals if v > 55.4)   / len(vals) * 100
    avg_cat, avg_color = aqi_cat(avg)

    stats = [
        ("Station",           station_name[:35]),
        ("Period",            f"Last {DAYS_BACK} days"),
        ("Average PM2.5",     f"{avg:.1f} µg/m³  →  {avg_cat}"),
        ("Peak reading",      f"{peak:.1f} µg/m³  ({peak_time})"),
        ("Time 'Good'",       f"{good_pct:.0f}% of readings"),
        ("Time 'Unhealthy'+", f"{bad_pct:.0f}% of readings"),
    ]
    y = 0.92
    ax4.text(0.05, y, "Summary", color="white", fontsize=12,
             fontweight="bold", transform=ax4.transAxes)
    y -= 0.1
    for label, value in stats:
        ax4.text(0.05, y,        label,
                 color="#888888", fontsize=9, transform=ax4.transAxes)
        ax4.text(0.05, y - 0.07, value,
                 color=avg_color if "Average" in label else "white",
                 fontsize=10, fontweight="bold", transform=ax4.transAxes)
        y -= 0.17

    plt.suptitle(f"Air Quality Dashboard — {CITY}", color="white",
                 fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    out = "air_quality_dashboard.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"\n✅  Saved!  Open with:  open {out}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\nFetching air quality data for {CITY}...\n")
    locations = get_locations()

    if not locations:
        print("❌ No stations found. Check your API key.")
    else:
        df = None
        station_name = ""
        for loc in locations:
            name = loc.get("name", str(loc.get("id", "unknown")))
            print(f"  Trying: {name}")
            sid = get_pm25_sensor(loc["id"])
            if not sid:
                print("    no PM2.5 sensor — skipping")
                continue
            df = get_measurements(sid)
            if df is not None:
                station_name = name
                print(f"    ✅ Got {len(df)} readings!")
                break
            else:
                print("    no data — trying next station")

        if df is None:
            print("\n❌ No data found. Try setting DAYS_BACK = 7 at the top.")
        else:
            print(f"\nBuilding dashboard from '{station_name}'...")
            build_dashboard(df, station_name)