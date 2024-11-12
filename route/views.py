from django.shortcuts import render
from django.http import JsonResponse
from fuel_routes import settings
from haversine import haversine
import requests
import time
import polyline
from math import radians, sin, cos, sqrt, atan2
from geopy.geocoders import Nominatim
import os
import json
import cProfile
import pstats
import io
from shapely.geometry import Point
import geopandas as gpd
import geopandas as gpd
import os
import pandas as pd

GOOGLE_API = settings.GOOGLE_API

# Directory containing state GeoJSON files
states_dir = 'usstatesgeojson-master'

# List to store GeoDataFrames for each state
states_gdf_list = []

# Loop through the files and read each state
for filename in os.listdir(states_dir):
    if filename.endswith('.geojson'):
        file_path = os.path.join(states_dir, filename)
        
        # Read each state's GeoJSON file into a GeoDataFrame
        state_gdf = gpd.read_file(file_path)
        
        # Extract the state name from the file name (e.g., "alabama.geojson" -> "Alabama")
        state_name = filename.split('.')[0].capitalize()
        state_gdf['name'] = state_name  # Add a column for the state name
        
        # Append to the list
        states_gdf_list.append(state_gdf)

# Combine all state GeoDataFrames into one GeoDataFrame
combined_states_gdf = gpd.GeoDataFrame(pd.concat(states_gdf_list, ignore_index=True))

# Helper function to generate waypoints between start and end coordinates
def generate_waypoints(start_lat, start_lng, end_lat, end_lng, num_points=50):
    lat_points = [start_lat + (end_lat - start_lat) * i / num_points for i in range(num_points + 1)]
    lng_points = [start_lng + (end_lng - start_lng) * i / num_points for i in range(num_points + 1)]
    return list(zip(lat_points, lng_points))

# Function to check which states a route passes through
def states_on_route(start_lat, start_lng, end_lat, end_lng):
    waypoints = generate_waypoints(start_lat, start_lng, end_lat, end_lng)
    
    states = set()
    for lat, lng in waypoints:
        point = Point(lng, lat)
        for _, state in combined_states_gdf.iterrows():
            if state['geometry'].contains(point):
                # Translate state name to its abbreviation
                abbrev = us_state_abbrev.get(state['name'], None)
                if abbrev:
                    states.add(abbrev)
                break
    return list(states)
# Create a Nominatim geocoder instance
geolocator = Nominatim(user_agent="route_state_finder")

us_state_abbrev = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA', 'Colorado': 'CO',
    'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
    'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
    'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC',
    'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA',
    'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX',
    'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY'
}

# Load JSON fuel prices data
def load_fuel_prices():
    with open(os.path.join(settings.BASE_DIR, 'fuel_prices.json'), 'r') as file:
        return json.load(file)
    

def fetch_route_data(request):
    # Create a StringIO object to capture profiling output
    pr = cProfile.Profile()
    pr.enable()  # Start profiling

    # Your existing code here (start_time, geocoding, route fetching, etc.)
    start_time = time.time()
    
    start_lat = request.GET.get('start_lat')
    start_lng = request.GET.get('start_lng')
    end_lat = request.GET.get('end_lat')
    end_lng = request.GET.get('end_lng')
    start_place = request.GET.get('start_place')
    end_place = request.GET.get('end_place')

    start_lat, start_lng = geocode_location(start_lat, start_lng, start_place)
    end_lat, end_lng = geocode_location(end_lat, end_lng, end_place)

    if not all([start_lat, start_lng, end_lat, end_lng]):
        return JsonResponse({"error": "Invalid locations provided."}, status=400)

    states = states_on_route(start_lat, start_lng, end_lat, end_lng)

    directions_url = f'https://maps.googleapis.com/maps/api/directions/json?origin={start_lat},{start_lng}&destination={end_lat},{end_lng}&key={GOOGLE_API}'
    response = requests.get(directions_url)

    if response.ok:
        data = response.json()
        if 'routes' not in data or not data['routes']:
            return JsonResponse({"error": "Route not found."}, status=404)

        total_distance_miles = data['routes'][0]['legs'][0]['distance']['value'] / 1609.34
        fuel_efficiency = 10
        total_gallons_needed = total_distance_miles / fuel_efficiency

        fuel_stops = load_fuel_prices()
        filtered_stops = [stop for stop in fuel_stops if stop['state'] in states]

        decoded_polyline = decode_polyline(data['routes'][0]['overview_polyline']['points'])
        selected_fuel_stops = select_fuel_stops(filtered_stops, decoded_polyline, distance_threshold=1, interval_miles=500)

        total_cost = sum(stop['price'] for stop in selected_fuel_stops) * total_gallons_needed

        context = {
            'start_coordinates': (start_lat, start_lng),
            'end_coordinates': (end_lat, end_lng),
            'fuel_stops': selected_fuel_stops,
            'total_cost': total_cost,
            'route': data['routes'][0],
            'maps': GOOGLE_API
        }
        print(f"Execution time: {time.time() - start_time:.2f} seconds")

        pr.disable()  # Stop profiling

        # Create a StringIO object to hold the profiling results
        s = io.StringIO()
        sortby = pstats.SortKey.CUMULATIVE
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)

        return render(request, "fetch_route.html", context)

    return JsonResponse({"error": "Route not found."}, status=404)


geocode_cache = {}

def geocode_location(lat, lng, place_name):
    # If latitude and longitude are provided, return them as floats
    if lat is not None and lng is not None:
        return float(lat), float(lng)

    # Check if the place name is already cached
    if place_name in geocode_cache:
        return geocode_cache[place_name]  # Return cached result

    # If place name is provided, perform geocoding
    if place_name:
        geocode_url = f'https://maps.googleapis.com/maps/api/geocode/json?address={place_name}&key={GOOGLE_API}'
        response = requests.get(geocode_url)
        
        # Check if the request was successful
        if response.ok:
            data = response.json()
            if data['results']:
                location = data['results'][0]['geometry']['location']
                result = (location['lat'], location['lng'])
                geocode_cache[place_name] = result  # Cache the result for future use
                
                return result

    # Return None if geocoding fails
    return None, None


def decode_polyline(polyline_str):
    return polyline.decode(polyline_str)

def select_fuel_stops(fuel_stops, decoded_polyline, distance_threshold=1, interval_miles=500):
    selected_fuel_stops = []
    segment_distance = 0
    cheapest_stop_in_segment = None
    min_price_in_segment = float('inf')

    for i, route_point in enumerate(decoded_polyline):
        if i > 0:
            segment_distance += calculate_distance(
                decoded_polyline[i - 1][0], decoded_polyline[i - 1][1],
                route_point[0], route_point[1]
            )
        for stop in fuel_stops:
            stop_lat = float(stop['latitude'])
            stop_lng = float(stop['longitude'])
            stop_price = float(stop['retail_price'])

            if is_within_distance_to_route(stop_lat, stop_lng, [route_point], distance_threshold):
                if stop_price < min_price_in_segment:
                    min_price_in_segment = stop_price
                    cheapest_stop_in_segment = stop

        if segment_distance >= interval_miles and cheapest_stop_in_segment:
            selected_fuel_stops.append({
                'name': cheapest_stop_in_segment['truckstop_name'],
                'address': cheapest_stop_in_segment['address'],
                'city': cheapest_stop_in_segment['city'],
                'state': cheapest_stop_in_segment['state'],
                'price': min_price_in_segment,
                'coordinates': [float(cheapest_stop_in_segment['latitude']), float(cheapest_stop_in_segment['longitude'])],
            })
            segment_distance = 0
            cheapest_stop_in_segment = None
            min_price_in_segment = float('inf')

    return selected_fuel_stops

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 3956  # Radius of the Earth in miles
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def is_within_distance_to_route(lat, lng, route_points, distance_threshold):
    stop_point = (lat, lng)
    for point in route_points:
        route_point = (point[0], point[1])
        distance = haversine(stop_point, route_point, unit="mi")
        if distance <= distance_threshold:
            return True
    return False
