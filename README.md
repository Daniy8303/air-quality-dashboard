# air-quality-dashboard
A Python tool that pulls real-time PM2.5 air pollution data from government monitoring stations and generates a visual dashboard for any US city.
Built using the OpenAQ API — an open-source platform aggregating air quality data from thousands of official sensors worldwide.


Why I built this

Air pollution causes an estimated 7 million premature deaths per year globally, yet most people have no easy way to understand the air quality data being collected in their own city. Government monitoring stations are constantly measuring PM2.5 (fine particulate matter — the most dangerous type of air pollution), but the raw data sits in databases most people never see.

I built this tool to make that data visual and accessible. By pulling 30 days of readings from the nearest monitoring station and generating a clear dashboard, anyone can see patterns in their city's air quality — which hours are worst, how often the air exceeds safe thresholds, and when pollution spikes occur.

What it shows
The dashboard has four panels:
Daily trend — PM2.5 average per day over the past 30 days, with EPA threshold lines marked

Hourly patterns — which hours of the day have the worst air quality on average (color-coded by AQI category)

AQI distribution — what percentage of readings fell into each EPA air quality category

Summary card — key statistics including average, peak reading, and percentage of "Good" vs "Unhealthy" days


AQI categories (EPA standard)
CategoryPM2.5 (µg/m³)Who is affectedGood0–12No health concernModerate12.1–35.4Unusually sensitive peopleUnhealthy for Sensitive Groups35.5–55.4Sensitive groups at risk
Unhealthy55.5–150.4Everyone may be affectedVery Unhealthy150.5–250.4Health alertHazardous250.5+Emergency conditions

Setup
Requirements

Python 3.8+
A free OpenAQ API key → openaq.org/developers

Install dependencies:
pip3 install requests matplotlib pandas

Configure:
Open air_quality.py and set your city and API key at the top

pythonCITY    = "New York"   # see supported cities below

API_KEY = "your_key_here"

Run
python air_quality.py
The dashboard saves as air_quality_dashboard.png in the same folder.

Supported cities
New York, Los Angeles, Chicago, Houston, Boston, Phoenix, Philadelphia, Seattle, Denver, Miami, Atlanta
To add a city, add its coordinates to the CITY_COORDS dictionary in the script.

What I found
Running this on New York City data (CCNY monitoring station, May 2026):

91% of readings fell in the "Good" category
Peak pollution occurred on November 29 at 11PM (60.0 µg/m³ — Unhealthy for Sensitive Groups)
Midday hours (11AM–1PM) consistently showed the highest average PM2.5, likely due to traffic and industrial activity
Air quality was notably cleaner in the early morning hours (3–5AM)

The November spike is worth investigating further — possible causes include weather inversion trapping pollution close to ground level, or a localized event near the monitoring station.

Next steps

 Add multi-city comparison (side-by-side dashboards)
 Add NO₂ and ozone layers alongside PM2.5
 Build a web interface so anyone can enter their city without coding
 Correlate pollution spikes with weather data (wind speed, temperature inversion)


Data source
All air quality data comes from OpenAQ, which aggregates measurements from official government monitoring networks including the US EPA AirNow program. Data is real — not modeled or estimated.

About
Built by a high school student interested in mechanical engineering, robotics, and using code to understand environmental systems.
