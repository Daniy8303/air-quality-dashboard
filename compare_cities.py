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
CITIES    = ["New York", "Los Angeles", "Chicago"]   # change any of these
DAYS_BACK = 30
API_KEY   = "fbc4b17d6a5292f91662ee197ff2c27df2fd79d59071069faa3baeaeaef34e99"
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

CITY_COLORS = ["#4a9eff", "#ff6b6b", "#ffd93d", "#6bcb77", "#c77dff"]


def get_locations(city):
    lat, lon = CITY_COORDS.get(city, (40.7128, -74.0060))
    r = requests.get(
        "https://api.openaq.org/v3/locations",
        headers=HEADERS,
        params={"coordinates": f"{lat},{lon}", "radius": 25000, "limit": 10},
        timeout=15,
    )
    return r.json().get("results", [])


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
                    val = item.get("value")
                    if val is None:
                        val = item.get("avg")
                    if val is None:
                        continue
                    val = float(val)
                    if val <= 0:
                        continue
                    period = item.get("period") or {}
                    dtf = period.get("datetimeFrom") or {}
                    raw = dtf.get("utc") or dtf.get("local")
                    if not raw:
                        raw = (item.get("datetime") or {}).get("utc") \
                           or (item.get("datetime") or {}).get("local")
                    if not raw:
                        continue
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
                return df.sort_values("datetime").reset_index(drop=True)
        except Exception:
            continue
    return None


def fetch_city_data(city):
    print(f"  Fetching {city}...")
    for loc in get_locations(city):
        sid = get_pm25_sensor(loc["id"])
        if not sid:
            continue
        df = get_measurements(sid)
        if df is not None:
            station = loc.get("name", "unknown")
            print(f"    ✅ {len(df)} readings from '{station}'")
            return df, station
    print(f"    ❌ No data found for {city}")
    return None, None


def aqi_cat(v):
    v = float(v)
    if v <= 12.0:    return "Good",                           "#00e400"
    elif v <= 35.4:  return "Moderate",                       "#ffff00"
    elif v <= 55.4:  return "Unhealthy for Sensitive Groups", "#ff7e00"
    elif v <= 150.4: return "Unhealthy",                      "#ff0000"
    elif v <= 250.4: return "Very Unhealthy",                 "#8f3f97"
    else:            return "Hazardous",                      "#7e0023"


def build_comparison(city_data):
    """
    city_data: list of (city_name, df, station_name)
    """
    n = len(city_data)
    fig = plt.figure(figsize=(16, 12))
    fig.patch.set_facecolor("#0f1117")

    def style(ax):
        ax.set_facecolor("#1a1d27")
        ax.tick_params(colors="#aaaaaa", labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333344")

    # ── Panel 1: overlaid daily trend ────────────────────────────────────────
    ax1 = fig.add_subplot(2, 2, 1)
    style(ax1)
    for i, (city, df, _) in enumerate(city_data):
        daily = df.set_index("datetime")["value"].resample("D").mean().dropna()
        color = CITY_COLORS[i % len(CITY_COLORS)]
        ax1.plot(daily.index, daily.values, color=color, linewidth=1.5,
                 label=city, zorder=2)
        ax1.fill_between(daily.index, daily.values, alpha=0.07, color=color)
    ax1.axhline(12.0, color="#00e400", lw=0.8, ls="--", alpha=0.6, label="Good threshold")
    ax1.axhline(35.4, color="#ffff00", lw=0.8, ls="--", alpha=0.6, label="Moderate threshold")
    ax1.set_title("PM2.5 Daily Average — All Cities", color="white", fontsize=11, pad=8)
    ax1.set_ylabel("PM2.5 (µg/m³)", color="#aaaaaa", fontsize=9)
    ax1.legend(fontsize=7, facecolor="#1a1d27", labelcolor="white", framealpha=0.5)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)

    # ── Panel 2: average PM2.5 bar chart ─────────────────────────────────────
    ax2 = fig.add_subplot(2, 2, 2)
    style(ax2)
    city_names = [c for c, _, _ in city_data]
    city_avgs  = [float(df["value"].mean()) for _, df, _ in city_data]
    bar_colors = [CITY_COLORS[i % len(CITY_COLORS)] for i in range(n)]
    bars = ax2.bar(city_names, city_avgs, color=bar_colors, width=0.5, edgecolor="none")
    ax2.axhline(12.0, color="#00e400", lw=0.8, ls="--", alpha=0.7)
    ax2.axhline(35.4, color="#ffff00", lw=0.8, ls="--", alpha=0.7)
    for bar, avg in zip(bars, city_avgs):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f"{avg:.1f}", ha="center", va="bottom",
                 color="white", fontsize=9, fontweight="bold")
    ax2.set_title("Average PM2.5 by City", color="white", fontsize=11, pad=8)
    ax2.set_ylabel("PM2.5 (µg/m³)", color="#aaaaaa", fontsize=9)

    # ── Panel 3: hourly pattern per city ─────────────────────────────────────
    ax3 = fig.add_subplot(2, 2, 3)
    style(ax3)
    for i, (city, df, _) in enumerate(city_data):
        df = df.copy()
        df["hour"] = df["datetime"].dt.hour
        hourly = df.groupby("hour")["value"].mean()
        color  = CITY_COLORS[i % len(CITY_COLORS)]
        ax3.plot(hourly.index, hourly.values, color=color,
                 linewidth=1.5, marker="o", markersize=3, label=city)
    ax3.set_title("PM2.5 by Hour of Day", color="white", fontsize=11, pad=8)
    ax3.set_xlabel("Hour (0 = midnight)", color="#aaaaaa", fontsize=9)
    ax3.set_ylabel("PM2.5 (µg/m³)", color="#aaaaaa", fontsize=9)
    ax3.set_xticks(range(0, 24, 3))
    ax3.legend(fontsize=7, facecolor="#1a1d27", labelcolor="white", framealpha=0.5)

    # ── Panel 4: summary table ────────────────────────────────────────────────
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.set_facecolor("#1a1d27")
    ax4.axis("off")

    col_labels = ["City", "Avg PM2.5", "Peak", "% Good", "% Unhealthy+"]
    rows = []
    for city, df, station in city_data:
        vals      = df["value"].tolist()
        avg       = float(sum(vals) / len(vals))
        peak      = float(max(vals))
        good_pct  = sum(1 for v in vals if v <= 12.0) / len(vals) * 100
        bad_pct   = sum(1 for v in vals if v > 55.4)  / len(vals) * 100
        cat, _    = aqi_cat(avg)
        rows.append([city, f"{avg:.1f} ({cat[:4]})", f"{peak:.1f}", f"{good_pct:.0f}%", f"{bad_pct:.0f}%"])

    tbl = ax4.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        bbox=[0, 0.2, 1, 0.75],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_facecolor("#252838" if row % 2 == 0 else "#1a1d27")
        cell.set_text_props(color="white")
        cell.set_edgecolor("#333344")
        if row == 0:
            cell.set_facecolor("#2a2d45")
            cell.set_text_props(color="#aaaaaa", fontweight="bold")

    ax4.set_title("City Comparison Summary", color="white", fontsize=11, pad=8)

    plt.suptitle(f"Air Quality Comparison — {', '.join(city_names)}",
                 color="white", fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    out = "city_comparison.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"\n✅  Saved!  Open with:  open {out}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\nFetching data for: {', '.join(CITIES)}\n")
    city_data = []
    for city in CITIES:
        df, station = fetch_city_data(city)
        if df is not None:
            city_data.append((city, df, station))

    if len(city_data) < 2:
        print("\n❌ Need at least 2 cities with data to compare.")
        print("Try changing the CITIES list at the top of the file.")
    else:
        print(f"\nBuilding comparison for {len(city_data)} cities...")
        build_comparison(city_data)