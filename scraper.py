import os
import requests
import csv
import json
import re
from io import StringIO
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

def main():
    print("Starting Restaurant Closure Geocoder...")
    os.makedirs('data', exist_ok=True)
    
    # The direct CSV export link for your Google Sheet
    sheet_url = "https://docs.google.com/spreadsheets/d/1QFulQSorSvySlYfBWkDbb1-USCq6oy8qz5nM7Iaj9_s/export?format=csv"
    
    try:
        response = requests.get(sheet_url)
        response.raise_for_status()
        
        reader = csv.reader(StringIO(response.text))
        next(reader) # Skip the header row
        
        features = []
        # Set up the free OpenStreetMap Geocoder
        geolocator = Nominatim(user_agent="sunsentinel_restaurant_tracker")
        # Add a 1.5-second delay between lookups so the server doesn't block the bot
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.5)
        
        for row in reader:
            # Skip empty rows
            if len(row) < 9:
                continue
                
            # Grab exactly the columns requested (Index is Column Letter minus 1)
            name = row[3].strip()     # Column D
            address = row[4].strip()  # Column E
            city = row[5].strip()     # Column F
            date = row[6].strip()     # Column G
            report_url = row[8].strip() # Column I
            
            if not name or not address:
                continue
                
            full_address = f"{address}, {city}, FL"
            print(f"Geocoding: {name} at {full_address}")
            
            try:
                # 1st Try: Look up the exact address
                location = geocode(full_address)
                
                # 2nd Try: Fallback if the first try fails due to suite/unit numbers
                if not location:
                    # Strip out common unit indicators (Ste, Suite, #, Unit, Apt)
                    cleaned_address = re.split(r'(?i)\s*(ste|suite|#|unit|apt|room)\s+', address)[0].strip()
                    fallback_address = f"{cleaned_address}, {city}, FL"
                    
                    if fallback_address != full_address:
                        print(f"  ⚠️ Retrying simplified address: {fallback_address}")
                        location = geocode(fallback_address)

                if location:
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [location.longitude, location.latitude]
                        },
                        "properties": {
                            "name": name,
                            "address": address, # Keep the original address for the popup display
                            "city": city,
                            "date": date,
                            "url": report_url
                        }
                    }
                    features.append(feature)
                else:
                    print(f"  ❌ Could not find coordinates for {full_address}")
            except Exception as e:
                print(f"  ❌ Error geocoding {full_address}: {e}")
                
        # Save the map-ready file
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        with open('data/closures.geojson', 'w') as f:
            json.dump(geojson, f)
            
        print(f"✅ Successfully mapped {len(features)} closed restaurants.")
        
    except Exception as e:
        print(f"❌ Error fetching sheet: {e}")

if __name__ == "__main__":
    main()