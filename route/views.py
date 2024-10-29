from django.shortcuts import render
from django.http import JsonResponse
from route.models import FuelPrice
from fuel_routes import settings
from haversine import haversine
import requests
import time
import polyline
from math import radians, sin, cos, sqrt, atan2


GOOGLE_API = settings.GOOGLE_API

def fetch_route_data(request):
    start_time = time.time()  # Start measuring time

    # Extract coordinates or place names from URL parameters
    start_lat = request.GET.get('start_lat')
    start_lng = request.GET.get('start_lng')
    end_lat = request.GET.get('end_lat')
    end_lng = request.GET.get('end_lng')
    
    start_place = request.GET.get('start_place')
    end_place = request.GET.get('end_place')

    # Geocode if necessary
    start_lat, start_lng = geocode_location(start_lat, start_lng, start_place)
    end_lat, end_lng = geocode_location(end_lat, end_lng, end_place)

    # Validate coordinates
    if not all([start_lat, start_lng, end_lat, end_lng]):
        return JsonResponse({"error": "Invalid locations provided."}, status=400)

    # Fetch route from Google Maps API
    directions_url = f'https://maps.googleapis.com/maps/api/directions/json?origin={start_lat},{start_lng}&destination={end_lat},{end_lng}&key={GOOGLE_API}'
    response = requests.get(directions_url)

    if response.ok:
        data = response.json()
        if 'routes' not in data or not data['routes']:
            return JsonResponse({"error": "Route not found."}, status=404)

        total_distance_miles = data['routes'][0]['legs'][0]['distance']['value'] / 1609.34
        fuel_efficiency = 10  # miles per gallon
        total_gallons_needed = total_distance_miles / fuel_efficiency

        # Pre-fetch fuel stops using geospatial queries
        fuel_stops = FuelPrice.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).values('truckstop_name', 'address', 'city', 'state', 'retail_price', 'latitude', 'longitude')

        # Decode the route polyline for distance calculations
        decoded_polyline = decode_polyline(data['routes'][0]['overview_polyline']['points'])

        # Optimize fuel stop selection
        selected_fuel_stops = select_fuel_stops(fuel_stops, start_lat, start_lng, decoded_polyline)

        # Calculate total cost based on selected stops
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
        return render(request, "fetch_route.html", context)

    return JsonResponse({"error": "Route not found."}, status=404)


def geocode_location(lat, lng, place_name):
    """Geocode a location if lat/lng are not provided."""
    if lat and lng:
        return float(lat), float(lng)
    if place_name:
        geocode_url = f'https://maps.googleapis.com/maps/api/geocode/json?address={place_name}&key={GOOGLE_API}'
        response = requests.get(geocode_url)
        if response.ok:
            data = response.json()
            if data['results']:
                location = data['results'][0]['geometry']['location']
                return location['lat'], location['lng']
    return None, None

def select_fuel_stops(fuel_stops, start_lat, start_lng, decoded_polyline):
    """Select fuel stops based on proximity to the route."""
    selected_fuel_stops = []
    current_distance_range = 0
    cheapest_stop_in_range = None
    distance_threshold = 3  # miles

    # Loop through each fuel stop and check if it's within distance
    for stop in fuel_stops:
        stop_lat = float(stop['latitude'])
        stop_lng = float(stop['longitude'])

        # Check if the fuel stop is close to the route
        if is_within_distance_to_route(stop_lat, stop_lng, decoded_polyline, distance_threshold):
            distance_to_stop = calculate_distance(start_lat, start_lng, stop_lat, stop_lng)

            if current_distance_range == 0:  # First stop
                current_distance_range += distance_to_stop
                cheapest_stop_in_range = stop
            else:
                current_distance_range += distance_to_stop

            if current_distance_range >= 500:  # Check if we have exceeded 500 miles
                if cheapest_stop_in_range:
                    selected_fuel_stops.append({
                        'name': cheapest_stop_in_range['truckstop_name'],
                        'address': cheapest_stop_in_range['address'],
                        'city': cheapest_stop_in_range['city'],
                        'state': cheapest_stop_in_range['state'],
                        'price': float(cheapest_stop_in_range['retail_price']),
                        'coordinates': [stop_lat, stop_lng],
                    })
                current_distance_range = 0
                cheapest_stop_in_range = None

    if cheapest_stop_in_range and current_distance_range > 0:
        selected_fuel_stops.append({
            'name': cheapest_stop_in_range['truckstop_name'],
            'address': cheapest_stop_in_range['address'],
            'city': cheapest_stop_in_range['city'],
            'state': cheapest_stop_in_range['state'],
            'price': float(cheapest_stop_in_range['retail_price']),
            'coordinates': [stop_lat, stop_lng],
        })

    return selected_fuel_stops


def decode_polyline(polyline_str):
    """Decode a Google Maps encoded polyline into a list of (lat, lng) tuples."""
    return polyline.decode(polyline_str)

def is_within_distance_to_route(lat, lng, route_points, distance_threshold):
    """Check if a fuel stop is within a certain distance (miles) to the route."""    
    stop_point = (lat, lng)
    
    for point in route_points:
        route_point = (point[0], point[1])
        distance = haversine(stop_point, route_point, unit='mi')
        if distance <= distance_threshold:
            return True
            
    return False

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate a distance between 2 places."""
    R = 3956  # Radius of the Earth in miles
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c  # Distance in miles
