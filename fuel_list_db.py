import sqlite3
import json
import os

# Path to the JSON file where the data will be saved
json_file_path = './fuel_prices.json'
database_path = './db.sqlite3'  # Adjust the path to your SQLite database if needed

# Function to load existing data from the JSON file
def load_json_data():
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as file:
            return json.load(file)
    return []

# Function to save data to the JSON file
def save_to_json(data):
    with open(json_file_path, 'w') as file:
        json.dump(data, file, indent=4)

# Load existing JSON data
fuel_data = load_json_data()

# Connect to the SQLite database
connection = sqlite3.connect(database_path)
cursor = connection.cursor()

# SQL query to fetch data from the table (adjust table and field names as needed)
query = '''
SELECT 
    opis_truckstop_id, 
    truckstop_name, 
    address, 
    city, 
    state, 
    rack_id, 
    retail_price, 
    latitude, 
    longitude 
FROM route_fuelprice  -- Adjust to the actual table name
'''

# Execute the query and process each row
for row in cursor.execute(query):
    # Create an entry dictionary with data from each row
    entry = {
        'opis_truckstop_id': row[0],
        'truckstop_name': row[1],
        'address': row[2],
        'city': row[3],
        'state': row[4],
        'rack_id': row[5],
        'retail_price': row[6],
        'latitude': row[7],
        'longitude': row[8]
    }
    # Append the entry to the list
    fuel_data.append(entry)

# Save all collected data to the JSON file
save_to_json(fuel_data)
print("Data loaded from database and saved to JSON successfully.")

# Close the database connection
connection.close()
