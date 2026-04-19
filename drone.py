import os
import random
import time
import math
import requests
from operator import sub
import pygame

BASE_URL = "http://127.0.0.1:5000"

class Warehouse:
    def __init__(self, name, latlon = (0, 0)):
        self.name = name
        self.id = ""
        self.loc = latlon

    def Register(self):
        payload = {
            "name": self.name,
            "lat": self.loc[0],
            "lon": self.loc[1]
        }
        try:
            response = requests.post(f"{BASE_URL}/register_warehouse", json=payload)
            response.raise_for_status() 
            data = response.json()
            self.id = data.get("id")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to register warehouse '{self.name}': {e}")
            if response is not None and response.text:
                print(f"Server response: {response.json()}")
            return False

class Drone:
    def __init__(self, name, latlon = (0, 0)):
        self.name = name
        self.id = ""
        self.status = "idle"
        self.loc = latlon
        self.pickup_warehouse_id = ""
        self.delivery_warehouse_id = ""
        self.owner = ""
        self.speed = 10

    def Register(self):
        payload = {
            "name": self.name
        }
        try:
            response = requests.post(f"{BASE_URL}/register_drone", json=payload)
            response.raise_for_status() 
            data = response.json()
            self.id = data.get("id")
            self.status = data.get("status", self.status) # Update status if provided by DB
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to register drone '{self.name}': {e}")
            if response is not None and response.text:
                print(f"Server response: {response.json()}")
            return False

    def GetDroneState(self):
        if not self.id:
            print(f"Cannot fetch state for '{self.name}': Drone has no ID (not registered).")
            return False
        try:
            response = requests.get(f"{BASE_URL}/get_drone/{self.id}")
            response.raise_for_status()
            data = response.json()
            # Update the local object state with fresh database data
            self.status = data.get("status", self.status)
            self.pickup_warehouse_id = data.get("pickup_warehouse_id", self.pickup_warehouse_id)
            self.delivery_warehouse_id = data.get("delivery_warehouse_id", self.delivery_warehouse_id)
            return True     
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch state for drone '{self.name}': {e}")
            return False

    def UpdateDroneState(self):
        if not self.id:
            print(f"Cannot update state for '{self.name}': Drone has no ID (not registered).")
            return False
        payload = {
            "status": self.status,
            "lat": self.loc[0],
            "lon": self.loc[1]
        }
        try:
            response = requests.put(f"{BASE_URL}/update_drone/{self.id}", json=payload)
            response.raise_for_status()
            return True     
        except requests.exceptions.RequestException as e:
            print(f"Failed to update state for drone '{self.name}': {e}")
            if response is not None and response.text:
                print(f"Server response: {response.json()}")
            return False

    def Update(self):
        if self.status == "idle":
            return
        current_dest = (0., 0.)
        if self.status == "pickup":
            current_dest = warehouses[self.pickup_warehouse_id].loc
        elif self.status == "deliver":
            current_dest = warehouses[self.delivery_warehouse_id].loc

        dist_vec = tuple(map(sub, current_dest, self.loc))
        dist = math.hypot(dist_vec[0], dist_vec[1])
        if dist <= self.speed:
            if self.status == "pickup":
                self.status = "deliver"
            else:
                self.status = "idle"
        else:
            unit_vec = (dist_vec[0] / dist, dist_vec[1] / dist)
            self.loc = (self.loc[0] + unit_vec[0] * self.speed, self.loc[1] + unit_vec[1] * self.speed)
        self.UpdateDroneState()

    def Log(self):
        print(f"Drone {self.name} location: {self.loc}")
        pass

def ResetTables():
    print("--- Dropping Drones Table ---")
    response = requests.delete(f"{BASE_URL}/drop_drones")
    print(response.json())
    print("\n--- Dropping Warehouses Table ---")
    response = requests.delete(f"{BASE_URL}/drop_warehouses")
    print(response.json())
    response = requests.post(f"{BASE_URL}/init_tables")
    print(response.json())

def GenerateRandomLocation():
    lat = random.uniform(-90, 90)
    lon = random.uniform(-180, 180)
    return (lat, lon)

def InitializeWarehouses():
    warehouses = {}
    wh_sfo = Warehouse("SFO", GenerateRandomLocation())
    wh_sfo.Register()
    wh_ord = Warehouse("ORD", GenerateRandomLocation())
    wh_ord.Register()
    wh_lga = Warehouse("LGA", GenerateRandomLocation())
    wh_lga.Register()
    warehouses[wh_sfo.id] = wh_sfo
    warehouses[wh_ord.id] = wh_ord
    warehouses[wh_lga.id] = wh_lga
    return warehouses

num_drones = 5
def InitializeDrones():
    drones = {f"drone_{i}": Drone(f"drone_{i}", GenerateRandomLocation()) for i in range(num_drones)}
    for name, drone in drones.items():
        drone.Register()
        drone.GetDroneState()
    return drones

ResetTables()
warehouses = InitializeWarehouses()
drones = InitializeDrones()

def AssignDrone():
    if len(warehouses) < 2:
        print("Error: Need at least 2 warehouses registered to assign a route.")
        return None

    pickup_id, delivery_id = random.sample(list(warehouses.keys()), 2)
    
    pickup_wh = warehouses[pickup_id]
    delivery_wh = warehouses[delivery_id]
    
    print(f"Requesting drone for pickup at '{pickup_wh.name}' ({pickup_wh.loc}) and delivery to '{delivery_wh.name}' ({delivery_wh.loc})...")

    # Calling API
    payload = {
        "pickup_warehouse_id": pickup_id,
        "delivery_warehouse_id": delivery_id
    }
    try:
        response = requests.post(f"{BASE_URL}/assign_drone", json=payload)
        response.raise_for_status() 

        data = response.json()
        
        assigned_drone = drones[data["name"]]
        assigned_drone.status = data["status"]
        assigned_drone.pickup_warehouse_id = data.get("pickup_warehouse_id")
        assigned_drone.delivery_warehouse_id = data.get("delivery_warehouse_id")
        
        print(f"Success! Drone '{assigned_drone.name}' (ID: {assigned_drone.id}) assigned.")
        return assigned_drone
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to assign drone: {e}")
        if 'response' in locals() and response is not None and response.status_code == 404:
            print("Reason: No idle drones available near the pickup location.")
        return None

"""
def StartSimulation():
    while True:
        idle_count = 0
        for name, drone in drones.items():
            drone.Update()
            drone.Log()
            if drone.status == "idle":
                idle_count += 1
        for i in range(idle_count):
            AssignDrone()
        time.sleep(1)
"""

# PyGame configs
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
BACKGROUND_COLOR = (0, 0, 0) # Black
WAREHOUSE_COLOR = (255, 255, 0) # Yellow
DRONE_COLOR = (0, 255, 0) # Green

MIN_LAT, MAX_LAT = -90, 90
MIN_LON, MAX_LON = -180, 180

# PyGame init
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Drone Fleet Simulation")
font = pygame.font.SysFont(None, 20)

def LatLonToScreenCoords(lat, lon):
    lat_range = max(MAX_LAT - MIN_LAT, 1e-6)
    lon_range = max(MAX_LON - MIN_LON, 1e-6)
    
    # Normalize between 0.0 and 1.0
    x_pct = (lon - MIN_LON) / lon_range
    y_pct = (lat - MIN_LAT) / lat_range
    
    # Scale to screen size.
    x = int(x_pct * SCREEN_WIDTH)
    y = int(SCREEN_HEIGHT - (y_pct * SCREEN_HEIGHT))
    
    return x, y

def StartSimulation():
    running = True
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        if not running:
            break

        # Background color
        screen.fill(BACKGROUND_COLOR)

        # Render warehouses (yellow squares)
        for warehouse_id, warehouse in warehouses.items():
            x, y = LatLonToScreenCoords(warehouse.loc[0], warehouse.loc[1])
            rect = pygame.Rect(x - 5, y - 5, 10, 10) 
            pygame.draw.rect(screen, WAREHOUSE_COLOR, rect)
            # Draw warehouse label
            label_text = f"{warehouse.name}"
            d_label = font.render(label_text, True, (200, 200, 200))
            screen.blit(d_label, (x + 10, y + 10))

        idle_count = 0
        for name, drone in drones.items():
            drone.Update()
            if drone.status == "idle":
                idle_count += 1
            drone.Log()

            # PyGame visualization
            x, y = LatLonToScreenCoords(drone.loc[0], drone.loc[1])
            pygame.draw.circle(screen, DRONE_COLOR, (x, y), 4)
            # Label drone
            label_text = f"{drone.name} ({drone.status})"
            if drone.status == "pickup" and drone.pickup_warehouse_id != "":
                label_text += (f" enroute to {warehouses[drone.pickup_warehouse_id].name}")
            elif drone.status == "deliver" and drone.delivery_warehouse_id != "":
                label_text += (f" enroute to {warehouses[drone.delivery_warehouse_id].name}")
            d_label = font.render(label_text, True, (200, 200, 200))
            screen.blit(d_label, (x + 10, y + 10))

        for i in range(idle_count):
            AssignDrone()

        # Render
        pygame.display.flip()

        time.sleep(1)

    pygame.quit()

# Main

if __name__ == "__main__":
    StartSimulation()
