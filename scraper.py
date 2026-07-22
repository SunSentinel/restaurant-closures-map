import os
import json
import time
import re
import csv
import urllib.request
import io
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# ==========================================
# 1. ADDRESS NORMALIZATION HELPER
# ==========================================
def normalize_street_name(address):
    """
    Cleans up addresses so Nominatim can read them.
    - Removes periods (e.g., "Nw." -> "NW")
    - Converts bare numbers to ordinals ONLY if followed by street designators
      (e.g., "2 Ave" -> "2nd Ave"), preserving highways (e.g., "State Road 7").
    """
    if not address:
        return ""
    
    # Remove periods
    address = address.replace('.', '')
    
    # Common street suffixes where a number preceding them should be ordinalized
    street_types = r'(Ave|Avenue|St|Street|Ter|Terrace|Ct|Court|Pl|Place|Ln|Lane|Way|Cir|Circle|Dr|Drive|Blvd|Boulevard)'
    
    def replace_ordinal(match):
        num = int(match.group(1))
        suffix_word = match.group(2)
        if 11 <= (num % 100) <= 13:
            sfx = 'th'
        else:
            sfx = {1: 'st', 2: 'nd', 3: 'rd'}.get(num % 10, 'th')
        return f"{num}{sfx} {suffix_word}"

    # Only convert numbers that immediately precede a street type
    address = re.sub(r'\b(\d+)\s+' + street_types + r'\b', replace_ordinal, address, flags=re.IGNORECASE)
    
    return address.strip()

# ==========================================
# 2. FETCH FROM PUBLIC GOOGLE SHEET
# ==========================================
print("Downloading data directly from Google Sheets...")

SHEET_ID = "1QFulQSorSvySlYfBWkDbb1-USCq6oy8qz5nM7Iaj9_s"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

req = urllib.request.Request(CSV_URL, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req)

# utf-8-sig removes the invisible BOM character on the first column
csv_data = response.read().decode('utf-8-sig')

reader = csv.DictReader(io.StringIO(csv_data))
raw_restaurants = []

for row in reader:
    # Mapped to your exact Google Sheet column headers
    name = row.get("Business (DBA-Does Business As) Name", "").strip()
    address = row.get("Location Address", "").strip()
    
    if name and address:
        raw_restaurants.append({
            "name": name,
            "address": address,
            "city": row.get("Location City", "").strip(), 
            "date": row.get("Inspection Date", "").strip(),
            "violations": row.get("Number of High Priority Violations", "").strip(),
            "url": row.get("Inspection Details URL", "").strip()
        })

print(f"Found {len(raw_restaurants)} restaurants in the Google Sheet.")

# ==========================================
# 3. GEOCODE AND BUILD GEOJSON
# ==========================================
print("Starting geocoding process...")

geolocator = Nominatim(user_agent="sun-sentinel-restaurant-closures-map")
features = []

for restaurant in raw_restaurants:
    clean_address = normalize_street_name(restaurant['address'])
    search_string = f"{clean_address}, {restaurant['city']}, FL"
    print(f"Geocoding: {search_string}")
    
    try:
        location = geolocator.geocode(search_string)
        
        if location:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [location.longitude, location.latitude]
                },
                "properties": {
                    "name": restaurant['name'],
                    "address": clean_address,
                    "city": restaurant['city'],
                    "date": restaurant['date'],
                    "violations": restaurant['violations'],
                    "url": restaurant['url']
                }
            }
            features.append(feature)
        else:
            print(f"  -> WARNING: Could not find coordinates for {search_string}")
            
        time.sleep(1)
        
    except GeocoderTimedOut:
        print(f"  -> ERROR: Geocoder timed out for {search_string}")
        time.sleep(2)

geojson_data = {
    "type": "FeatureCollection",
    "features": features
}

print(f"\nSuccessfully mapped {len(features)} out of {len(raw_restaurants)} restaurants.")

# ==========================================
# 4. SAVE USING BULLETPROOF ABSOLUTE PATH
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, 'data', 'closures.geojson')

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(geojson_data, f, indent=2)

print(f"Data successfully saved to: {OUTPUT_PATH}")