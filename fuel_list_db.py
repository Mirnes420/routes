import os
import django
import csv
import requests
import time

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fuel_routes.settings')
django.setup()

# Now import your model
from route.models import FuelPrice

# Path to your CSV file
csv_file_path = './fuel-prices-for-be-assessment.csv'

# Google Maps Geocoding API Key
GOOGLE_MAPS_API_KEY = 'AIzaSyAsYmjElecB7_eXthdJw5OP_IcHEJbERzs'

# Function to get latitude and longitude from address
def get_lat_long(address, retries=3):
    for attempt in range(retries):
        try:
            # Google Maps Geocoding API endpoint
            response = requests.get('https://maps.googleapis.com/maps/api/geocode/json', params={
                'address': address,
                'key': GOOGLE_MAPS_API_KEY
            })

            # Check if the request was successful
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'OK':
                    return float(data['results'][0]['geometry']['location']['lat']), float(data['results'][0]['geometry']['location']['lng'])
                else:
                    print(f"No data found for address: {address}, Status: {data['status']}")
                    return None, None
            else:
                print(f"Request failed with status code {response.status_code} for address: {address}")
                return None, None
        except Exception as e:
            print(f"Error getting coordinates for {address}: {e}")
            if attempt < retries - 1:
                time.sleep(1)  # Wait before retrying
            else:
                return None, None

# Load data from CSV
with open(csv_file_path, newline='') as csvfile:
    reader = csv.DictReader(csvfile, delimiter=',')  # Use comma in the CSV file

    for row in reader:
        # Construct the full address, stripping any leading/trailing spaces
        full_address = f"{row['Address'].strip()}, {row['City'].strip()}, {row['State'].strip()}"

        # Get latitude and longitude using the full address
        latitude, longitude = get_lat_long(full_address)

        # If not found, try using just the city and state
        if latitude is None or longitude is None:
            city_state_address = f"{row['City'].strip()}, {row['State'].strip()}"
            print(f"Retrying with city and state: {city_state_address}")
            latitude, longitude = get_lat_long(city_state_address)

        # Create a FuelPrice entry if coordinates are found
        if latitude is not None and longitude is not None:
            FuelPrice.objects.create(
                opis_truckstop_id=row['OPIS Truckstop ID'],
                truckstop_name=row['Truckstop Name'],
                address=row['Address'],  # Store the original address
                city=row['City'],
                state=row['State'],
                rack_id=row['Rack ID'],
                retail_price=row['Retail Price'],
                latitude=latitude,
                longitude=longitude
            )
        else:
            print(f"Failed to retrieve coordinates for address: {full_address} and city/state: {city_state_address}")

        time.sleep(1)  # Add a delay between requests to avoid rate limiting

print("Data loaded successfully.")
