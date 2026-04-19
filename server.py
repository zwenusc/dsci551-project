import os
import random
import time
import math
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify

# SQL query definitions

create_table_warehouses_sql = """
CREATE TABLE warehouses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name STRING,
  location GEOGRAPHY,
  INDEX name_index (name),
  INVERTED INDEX location_index (location)
);
"""

create_table_drones_sql = """
DROP TYPE drone_status;
CREATE TYPE drone_status AS ENUM ('deliver', 'idle', 'pickup');
CREATE TABLE drones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
  name STRING,
  location GEOGRAPHY,
  location_last_updated TIMESTAMPTZ,
  status drone_status,
  pickup_warehouse_id UUID REFERENCES warehouses (id) ON DELETE SET NULL,
  delivery_warehouse_id UUID REFERENCES warehouses (id) ON DELETE SET NULL,
  INDEX name_index (name),
  INVERTED INDEX location_index (location),
  INVERTED INDEX status_location (status, location)
);
"""

drop_table_drones_sql = """
DROP TABLE IF EXISTS drones CASCADE;
"""

drop_table_warehouses_sql = """
DROP TABLE IF EXISTS warehouses CASCADE;
"""

get_drone_sql = """
SELECT id, name, ST_AsText(location) AS location, location_last_updated, status FROM drones;
"""

get_all_drones_sql = """
SELECT id, name, ST_AsText(location) AS location, location_last_updated, status FROM drones;
"""

insert_drone_sql = """
INSERT INTO drones (name) VALUES (%s);
"""

insert_and_return_drone_sql = """
INSERT INTO drones (name) VALUES (%s) 
RETURNING id::STRING, name, ST_AsText(location) as location, location_last_updated::STRING, status;
"""

insert_and_return_warehouse_sql = """
INSERT INTO warehouses (name, location) 
VALUES (%s, %s::GEOGRAPHY) 
RETURNING id::STRING, name, ST_AsText(location) AS location;
"""

get_drone_by_id_sql = """
SELECT id::STRING, name, ST_AsText(location) AS location, location_last_updated::STRING, status 
FROM drones WHERE id = %s;
"""

update_drone_sql = """
UPDATE drones
SET location = %s::GEOGRAPHY,
location_last_updated = now(),
status = %s
WHERE id = %s;
"""

get_warehouse_location_sql = """
SELECT ST_AsText(location) AS location FROM warehouses WHERE id = %s;
"""

assign_drone_sql = """
UPDATE drones
SET status = 'pickup',
    pickup_warehouse_id = %s,
    delivery_warehouse_id = %s
WHERE id = (
    SELECT id
    FROM drones
    WHERE status = 'idle'
    ORDER BY ST_Distance(location, %s::GEOGRAPHY)
    LIMIT 1
    FOR UPDATE
)
RETURNING id::STRING, name, ST_AsText(location) AS location, location_last_updated::STRING, status, pickup_warehouse_id::STRING, delivery_warehouse_id::STRING;
"""

# API

app = Flask(__name__)
conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True

def FormatLatLon(lat: float, lon: float):
    return f"POINT({lat} {lon})"

@app.route('/register_drone', methods=['POST'])
def register_drone():
    data = request.get_json()
    name = data.get('name')
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(insert_and_return_drone_sql, (name,))
        drone = cur.fetchone()
        
    return jsonify(drone), 201

@app.route('/register_warehouse', methods=['POST'])
def register_warehouse():
    data = request.get_json()
    name = data.get('name')
    lat = data.get('lat')
    lon = data.get('lon')
    
    if not name or lat is None or lon is None:
        return jsonify({"error": "Missing required fields: name, lat, lon"}), 400
        
    location_point = FormatLatLon(lat, lon)
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(insert_and_return_warehouse_sql, (name, location_point))
            warehouse = cur.fetchone()
        return jsonify(warehouse), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/get_drone/<drone_id>', methods=['GET'])
def get_drone(drone_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(get_drone_by_id_sql, (drone_id,))
        drone = cur.fetchone()
        
    if not drone:
        return jsonify({"error": "Drone not found"}), 404
    return jsonify(drone), 200

@app.route('/update_drone/<drone_id>', methods=['PUT'])
def update_drone(drone_id):
    data = request.get_json()
    lat = data.get('lat')
    lon = data.get('lon')
    status = data.get('status')
    
    point = FormatLatLon(lat, lon)
    
    try:
        with conn.cursor() as cur:
            cur.execute(update_drone_sql, (point, status, drone_id))
            if cur.rowcount == 0:
                return jsonify({"success": False, "error": "Drone not found"}), 404
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/assign_drone', methods=['POST'])
def assign_drone():
    data = request.get_json()
    pickup_warehouse_id = data.get('pickup_warehouse_id')
    delivery_warehouse_id = data.get('delivery_warehouse_id')
    
    if not pickup_warehouse_id or not delivery_warehouse_id:
         return jsonify({"error": "Missing pickup_warehouse_id or delivery_warehouse_id"}), 400
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Step 1: Look up the location of the pickup warehouse
        cur.execute(get_warehouse_location_sql, (pickup_warehouse_id,))
        warehouse = cur.fetchone()
        
        if not warehouse or not warehouse['location']:
            return jsonify({"error": "Pickup warehouse not found or has no location"}), 404
            
        pickup_location_wkt = warehouse['location']
        
        # Step 2: Find the closest idle drone to that location and assign it
        cur.execute(assign_drone_sql, (
            pickup_warehouse_id, 
            delivery_warehouse_id, 
            pickup_location_wkt
        ))
        drone = cur.fetchone()
        
    if not drone:
        return jsonify({"error": "No idle drones available"}), 404
        
    return jsonify(drone), 200

@app.route('/init_tables', methods=['POST'])
def init_database():
    """Creates all tables in the correct dependency order."""
    try:
        with conn.cursor() as cur:
            cur.execute(create_table_warehouses_sql)
            cur.execute(create_table_drones_sql)
        return jsonify({"success": True, "message": "Database schema initialized successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/drop_drones', methods=['DELETE'])
def drop_drones():
    """Drops the drones table for demo convenience."""
    try:
        with conn.cursor() as cur:
            cur.execute(drop_table_drones_sql)
        return jsonify({"success": True, "message": "Drones table dropped successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/drop_warehouses', methods=['DELETE'])
def drop_warehouses():
    """Drops the warehouses table for demo convenience."""
    try:
        with conn.cursor() as cur:
            cur.execute(drop_table_warehouses_sql)
        return jsonify({"success": True, "message": "Warehouses table dropped successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
