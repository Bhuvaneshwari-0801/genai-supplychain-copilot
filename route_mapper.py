import folium
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MAPBOX_API_KEY = os.getenv('MAPBOX_API_KEY')

def get_road_route_geometry(origin_coords, dest_coords):
    try:
        url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{origin_coords[1]},{origin_coords[0]};{dest_coords[1]},{dest_coords[0]}"
        params = {
            "access_token": MAPBOX_API_KEY,
            "geometries": "geojson",
            "overview": "full"
        }
        
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("routes"):
                coords = data["routes"][0]["geometry"]["coordinates"]
                return [[coord[1], coord[0]] for coord in coords]
    except Exception as e:
        print(f"Road routing error: {e}")
    
    return [origin_coords, dest_coords]

def get_sea_route_path(origin_port_coords, dest_port_coords):
    sea_waypoints = [
        origin_port_coords,
        [37.7, -123.0],
        [38.5, -123.5],
        [40.0, -124.2],
        [42.0, -124.8],
        [44.0, -125.0],
        [46.0, -124.8],
        [47.2, -124.5],
        [47.4, -123.0],
        dest_port_coords
    ]
    return sea_waypoints

def create_route_map(air_route=None, road_route=None, sea_route=None):
    m = folium.Map(location=[42.0, -120.0], zoom_start=5)
    
    route_styles = {
        'air': {'color': 'red', 'weight': 3, 'opacity': 0.8, 'dash_array': '10,5'},
        'road': {'color': 'blue', 'weight': 4, 'opacity': 0.9},
        'sea': {'color': 'green', 'weight': 3, 'opacity': 0.8}
    }
    
    if air_route:
        sjo_coords = [37.3639, -121.9289]
        sea_coords = [47.4502, -122.3088]
        
        air_path = [
            [sjo_coords[0] + 0.1, sjo_coords[1] + 0.1],
            [sea_coords[0] + 0.1, sea_coords[1] + 0.1]
        ]
        
        folium.PolyLine(
            locations=air_path,
            **route_styles['air'],
            popup=f"Air Route - Distance: {air_route.get('distance', 'N/A')} km"
        ).add_to(m)
        
        folium.Marker(sjo_coords, popup="San Jose Airport", 
                     icon=folium.Icon(color='red', icon='plane')).add_to(m)
        folium.Marker(sea_coords, popup="Seattle Airport", 
                     icon=folium.Icon(color='red', icon='plane')).add_to(m)
    
    if road_route:
        milpitas_coords = [37.4323, -121.8995]
        seattle_coords = [47.6062, -122.3321]
        
        road_geometry = get_road_route_geometry(milpitas_coords, seattle_coords)
        
        folium.PolyLine(
            locations=road_geometry,
            **route_styles['road'],
            popup=f"Road Route - Distance: {road_route.get('distance', 'N/A')} km"
        ).add_to(m)
        
        folium.Marker(milpitas_coords, popup="Origin: Milpitas", 
                     icon=folium.Icon(color='blue', icon='truck')).add_to(m)
        folium.Marker(seattle_coords, popup="Destination: Seattle", 
                     icon=folium.Icon(color='blue', icon='truck')).add_to(m)
    
    if sea_route:
        oakland_coords = [37.8044, -122.2711]
        seattle_port_coords = [47.6062, -122.3321]
        
        sea_path = get_sea_route_path(oakland_coords, seattle_port_coords)
        
        folium.PolyLine(
            locations=sea_path,
            **route_styles['sea'],
            popup=f"Sea Route - Distance: {sea_route.get('distance', 'N/A')} km"
        ).add_to(m)
        
        folium.Marker(oakland_coords, popup="Port of Oakland", 
                     icon=folium.Icon(color='green', icon='anchor')).add_to(m)
        folium.Marker(seattle_port_coords, popup="Port of Seattle", 
                     icon=folium.Icon(color='green', icon='anchor')).add_to(m)
    
    return m
