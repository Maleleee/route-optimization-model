import os
import requests
import pandas as pd
import folium
from itertools import permutations
from tqdm import tqdm
import numpy as np
import time
from dotenv import load_dotenv
import polyline
import json
import pickle
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Get MapQuest API key from environment variables
MAPQUEST_API_KEY = os.getenv("MAPQUEST_API_KEY")
if not MAPQUEST_API_KEY:
    print("Error: MAPQUEST_API_KEY not found in .env file.")
    print("Please add your API key to the .env file.")
    exit(1)

# File to cache route geometries
GEOMETRY_CACHE_FILE = "route_geometries_cache.pkl"

def load_geometry_cache():
    """Load cached route geometries from file if it exists"""
    if Path(GEOMETRY_CACHE_FILE).exists():
        try:
            with open(GEOMETRY_CACHE_FILE, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading geometry cache: {e}")
    return {}

def save_geometry_cache(cache):
    """Save route geometries to cache file"""
    try:
        with open(GEOMETRY_CACHE_FILE, 'wb') as f:
            pickle.dump(cache, f)
    except Exception as e:
        print(f"Error saving geometry cache: {e}")

# Load cached geometries at startup
geometry_cache = load_geometry_cache()

def geocode_address(address):
    """Use MapQuest to geocode address"""
    url = "http://www.mapquestapi.com/geocoding/v1/address"
    params = {
        "key": MAPQUEST_API_KEY,
        "location": address,
        "maxResults": 1
    }
    
    # Add Philippines to address if not already specified
    if "philippines" not in address.lower():
        params["location"] = f"{address}, Philippines"
    
    # Try up to 3 times with backoff
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if len(data["results"]) > 0 and len(data["results"][0]["locations"]) > 0:
                    loc = data["results"][0]["locations"][0]["latLng"]
                    if loc["lat"] != 39.78373 and loc["lng"] != -100.445882:  # MapQuest's default center of US
                        return (loc["lat"], loc["lng"])
            
            # Wait before retrying
            time.sleep(1.5 * attempt)
        except Exception as e:
            print(f"Error geocoding address (attempt {attempt+1}): {address}, Error: {e}")
            time.sleep(1.5 * attempt)
    
    print(f"Could not geocode address after multiple attempts: {address}")
    return None

def get_route_with_geometry(source, destination):
    """Get route information and geometry using OSRM public API with improved reliability"""
    if source is None or destination is None:
        return float("inf"), float("inf"), None
    
    # Check if we have this route in cache
    cache_key = (f"{source[0]:.6f},{source[1]:.6f}", f"{destination[0]:.6f},{destination[1]:.6f}")
    if cache_key in geometry_cache:
        cached_data = geometry_cache[cache_key]
        return cached_data["duration"], cached_data["distance"], cached_data["geometry"]
        
    source_lat, source_lon = source
    dest_lat, dest_lon = destination
    
    # Try OSRM API with multiple attempts
    success = False
    for attempt in range(3):
        try:
            # Use OSRM API to get the actual road geometry
            url = f"http://router.project-osrm.org/route/v1/driving/{source_lon},{source_lat};{dest_lon},{dest_lat}"
            params = {
                "overview": "full",  # Get the full route geometry
                "geometries": "polyline",  # Use encoded polyline format
                "steps": "false",
                "alternatives": "false",
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data["code"] == "Ok":
                    route = data["routes"][0]
                    duration_seconds = route["duration"]
                    distance_meters = route["distance"]
                    geometry = route["geometry"]  # This is the encoded polyline
                    
                    # Decode the polyline to get the list of coordinates
                    coords = polyline.decode(geometry)
                    
                    # Cache this successful result
                    geometry_cache[cache_key] = {
                        "duration": duration_seconds,
                        "distance": distance_meters,
                        "geometry": coords
                    }
                    
                    # Save cache periodically (every 10 routes)
                    if len(geometry_cache) % 10 == 0:
                        save_geometry_cache(geometry_cache)
                    
                    return duration_seconds, distance_meters, coords
            
            # Increase wait time between retries
            time.sleep(2 * (attempt + 1))
        except Exception as e:
            print(f"Exception with OSRM routing (attempt {attempt+1}): {e}")
            time.sleep(2 * (attempt + 1))
    
    # If all OSRM attempts failed, try MapQuest
    print(f"OSRM routing failed after multiple attempts, falling back to MapQuest for {source} to {destination}")
    return get_mapquest_route(source, destination)

def get_mapquest_route(source, destination):
    """Fallback to MapQuest for route information and geometry with improved reliability"""
    source_lat, source_lon = source
    dest_lat, dest_lon = destination
    
    # Check if we have this route in cache (using different service but same points)
    cache_key = (f"{source_lat:.6f},{source_lon:.6f}", f"{dest_lat:.6f},{dest_lon:.6f}")
    if cache_key in geometry_cache and geometry_cache[cache_key].get("service") == "mapquest":
        cached_data = geometry_cache[cache_key]
        return cached_data["duration"], cached_data["distance"], cached_data["geometry"]
    
    # Try MapQuest API with multiple attempts
    for attempt in range(3):
        try:
            url = "http://www.mapquestapi.com/directions/v2/route"
            params = {
                "key": MAPQUEST_API_KEY,
                "from": f"{source_lat},{source_lon}",
                "to": f"{dest_lat},{dest_lon}",
                "unit": "k",  # kilometers
                "routeType": "fastest",
                "doReverseGeocode": "false",
                "fullShape": "true"  # Get the full route shape
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("route") and data["route"].get("distance") is not None:
                    distance_km = data["route"]["distance"]
                    duration_seconds = data["route"]["time"]
                    
                    # Extract the route's shape points
                    shape_points = data["route"].get("shape", {}).get("shapePoints", [])
                    if shape_points and len(shape_points) > 1:
                        # Convert the shape points from the format [lat1, lng1, lat2, lng2, ...] 
                        # to a list of coordinate pairs [(lat1, lng1), (lat2, lng2), ...]
                        coords = [(shape_points[i], shape_points[i+1]) for i in range(0, len(shape_points), 2)]
                        
                        # Cache this successful result
                        geometry_cache[cache_key] = {
                            "duration": duration_seconds,
                            "distance": distance_km * 1000,
                            "geometry": coords,
                            "service": "mapquest"
                        }
                        
                        # Save cache periodically
                        if len(geometry_cache) % 10 == 0:
                            save_geometry_cache(geometry_cache)
                        
                        return duration_seconds, distance_km * 1000, coords
            
            # Increase wait time between retries
            time.sleep(2 * (attempt + 1))
        except Exception as e:
            print(f"Exception with MapQuest routing (attempt {attempt+1}): {e}")
            time.sleep(2 * (attempt + 1))
    
    print(f"Error getting route after multiple attempts")
    return float("inf"), float("inf"), None

def create_interactive_map(df, best_order, route_geometries, distance_matrix, duration_matrix, total_km, total_hours):
    """Create an interactive map with route visualization and sidebar"""
    # Calculate the center point for the map
    map_center = [np.mean([coord[0] for coord in df["Coords"] if coord is not None]), 
                  np.mean([coord[1] for coord in df["Coords"] if coord is not None])]
    
    # Create the map with improved styling
    route_map = folium.Map(
        location=map_center, 
        zoom_start=11,
        tiles='OpenStreetMap',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    )
    
    # Create feature groups for different layers
    optimized_route_group = folium.FeatureGroup(name="Optimized Route", show=True)
    custom_route_group = folium.FeatureGroup(name="Custom Route", show=False)
    markers_group = folium.FeatureGroup(name="Delivery Stops", show=True)
    
    # Add markers for all locations with improved styling
    for i, row in df.iterrows():
        if i == 0:  # Warehouse
            icon = folium.Icon(color='red', icon='home', prefix='fa')
            popup_text = f"<div style='font-family: Arial, sans-serif;'><strong style='color: #ea4335;'>{row['Label']}</strong><br>{row['Address']}</div>"
        else:
            icon = folium.Icon(color='blue', icon='building', prefix='fa')
            popup_text = f"<div style='font-family: Arial, sans-serif;'><strong style='color: #1a73e8;'>{row['Label']}</strong><br>{row['Address']}</div>"
        
        folium.Marker(
            location=row["Coords"],
            popup=folium.Popup(popup_text, max_width=300),
            icon=icon,
            tooltip=f"<div style='font-family: Arial, sans-serif;'>{row['Label']}</div>"
        ).add_to(markers_group)
    
    # Add route lines with actual road geometry
    for i in range(len(best_order) - 1):
        start_idx = best_order[i]
        end_idx = best_order[i + 1]
        
        # Get the route geometry between these points
        route_key = (start_idx, end_idx)
        if route_key in route_geometries and route_geometries[route_key]:
            path = route_geometries[route_key]
            
            # Calculate stats for this leg
            distance_km = distance_matrix[start_idx, end_idx] / 1000  # Convert to km
            duration_min = duration_matrix[start_idx, end_idx] / 60  # Convert to minutes
            
            # Create a detailed popup for the route segment
            popup_text = f"""
            <div style='font-family: Arial, sans-serif; min-width: 200px'>
                <div style='border-bottom: 2px solid #34a853; margin-bottom: 8px; padding-bottom: 4px;'>
                    <strong style='color: #202124; font-size: 14px;'>Route Segment {i+1}</strong>
                </div>
                <div style='margin-bottom: 5px;'>
                    <span style='color: #5f6368;'>From:</span> <strong>{df.iloc[start_idx]['Label']}</strong>
                </div>
                <div style='margin-bottom: 8px;'>
                    <span style='color: #5f6368;'>To:</span> <strong>{df.iloc[end_idx]['Label']}</strong>
                </div>
                <div style='display: flex; justify-content: space-between; margin-top: 8px; border-top: 1px solid #e8eaed; padding-top: 8px;'>
                    <div>
                        <span style='color: #5f6368; font-size: 12px;'>Distance</span><br>
                        <strong style='color: #1a73e8;'>{distance_km:.1f} km</strong>
                    </div>
                    <div>
                        <span style='color: #5f6368; font-size: 12px;'>Est. Time</span><br>
                        <strong style='color: #1a73e8;'>{duration_min:.0f} min</strong>
                    </div>
                </div>
            </div>
            """
            
            # Add the actual road path with improved styling
            folium.PolyLine(
                locations=path,
                color='#0b8043',
                weight=6,
                opacity=0.9,
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"<div style='font-family: Arial, sans-serif;'>{df.iloc[start_idx]['Label']} → {df.iloc[end_idx]['Label']}</div>"
            ).add_to(optimized_route_group)
        else:
            # Fallback to straight line if no geometry available
            start_coords = df.iloc[start_idx]["Coords"]
            end_coords = df.iloc[end_idx]["Coords"]
            
            # Calculate stats for this leg
            distance_km = distance_matrix[start_idx, end_idx] / 1000  # Convert to km
            duration_min = duration_matrix[start_idx, end_idx] / 60  # Convert to minutes
            
            # Create a detailed popup for the route segment
            popup_text = f"""
            <div style='font-family: Arial, sans-serif; min-width: 200px'>
                <div style='border-bottom: 2px solid #ea4335; margin-bottom: 8px; padding-bottom: 4px;'>
                    <strong style='color: #202124; font-size: 14px;'>Route Segment {i+1}</strong>
                    <div style='color: #ea4335; font-size: 12px;'>(Road data unavailable)</div>
                </div>
                <div style='margin-bottom: 5px;'>
                    <span style='color: #5f6368;'>From:</span> <strong>{df.iloc[start_idx]['Label']}</strong>
                </div>
                <div style='margin-bottom: 8px;'>
                    <span style='color: #5f6368;'>To:</span> <strong>{df.iloc[end_idx]['Label']}</strong>
                </div>
                <div style='display: flex; justify-content: space-between; margin-top: 8px; border-top: 1px solid #e8eaed; padding-top: 8px;'>
                    <div>
                        <span style='color: #5f6368; font-size: 12px;'>Distance</span><br>
                        <strong style='color: #1a73e8;'>{distance_km:.1f} km</strong>
                    </div>
                    <div>
                        <span style='color: #5f6368; font-size: 12px;'>Est. Time</span><br>
                        <strong style='color: #1a73e8;'>{duration_min:.0f} min</strong>
                    </div>
                </div>
            </div>
            """
            
            folium.PolyLine(
                locations=[start_coords, end_coords],
                color='#d93025',  # Use red to indicate missing road data
                weight=4,
                opacity=0.9,
                dash_array='5, 10',
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"<div style='font-family: Arial, sans-serif;'>{df.iloc[start_idx]['Label']} → {df.iloc[end_idx]['Label']} (no road data)</div>"
            ).add_to(optimized_route_group)
        
        # Add a marker for the route number with improved styling
        mid_point = df.iloc[end_idx]["Coords"]
        folium.Marker(
            location=mid_point,
            icon=folium.DivIcon(html=f"""
                <div style='
                    font-size: 12px;
                    color: white;
                    background-color: #0b8043;
                    width: 24px;
                    height: 24px;
                    border-radius: 50%;
                    line-height: 24px;
                    text-align: center;
                    font-weight: bold;
                    font-family: Arial, sans-serif;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    border: 2px solid white;'
                >{i+1}</div>
            """),
        ).add_to(optimized_route_group)
    
    # Add all feature groups to the map
    markers_group.add_to(route_map)
    optimized_route_group.add_to(route_map)
    custom_route_group.add_to(route_map)
    
    # Add layer control with improved styling
    folium.LayerControl(position='topright').add_to(route_map)
    
    # Make feature groups available to JavaScript
    route_map.get_root().html.add_child(folium.Element("""
        <script>
            // Store feature groups globally
            window.optimized_route_group = null;
            window.custom_route_group = null;
            window.markers_group = null;
            window.map = null;
            
            // Function to initialize feature groups
            function initializeFeatureGroups() {
                // Get the map instance
                var maps = document.querySelectorAll('.folium-map');
                if (maps.length === 0) {
                    console.log('Map not found, retrying...');
                    setTimeout(initializeFeatureGroups, 100);
                    return;
                }
                
                // Get the Leaflet map instance
                var mapElement = maps[0];
                var mapId = mapElement.id;
                window.map = L.DomUtil.get(mapId)._leaflet_map;
                
                if (!window.map) {
                    console.log('Leaflet map not initialized, retrying...');
                    setTimeout(initializeFeatureGroups, 100);
                    return;
                }
                
                // Find feature groups by their names
                window.map.eachLayer(function(layer) {
                    if (layer instanceof L.FeatureGroup) {
                        if (layer.options.name === "Optimized Route") {
                            window.optimized_route_group = layer;
                        } else if (layer.options.name === "Custom Route") {
                            window.custom_route_group = layer;
                        } else if (layer.options.name === "Delivery Stops") {
                            window.markers_group = layer;
                        }
                    }
                });
                
                // Verify all groups are initialized
                if (window.optimized_route_group && window.custom_route_group && window.markers_group) {
                    console.log('All feature groups initialized successfully');
                } else {
                    console.log('Some feature groups not initialized, retrying...');
                    setTimeout(initializeFeatureGroups, 100);
                }
            }
            
            // Initialize when document is ready
            document.addEventListener('DOMContentLoaded', function() {
                console.log('Document ready, initializing feature groups...');
                initializeFeatureGroups();
                
                // Style the layer control
                setTimeout(function() {
                    const layerControls = document.querySelectorAll('.leaflet-control-layers');
                    if (layerControls.length > 0) {
                        layerControls.forEach(control => {
                            control.style.fontFamily = 'Arial, sans-serif';
                            control.style.borderRadius = '8px';
                            control.style.overflow = 'hidden';
                            control.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
                        });
                    }
                }, 500);
            });
            
            // Also try to initialize when the map is loaded
            window.addEventListener('load', function() {
                console.log('Window loaded, checking feature groups initialization...');
                initializeFeatureGroups();
            });
        </script>
    """))
    
    # Add an improved legend with better styling
    legend_html = '''
    <div id="mapLegend" style="
        position: fixed; 
        bottom: 20px; 
        right: 20px; 
        width: 240px; 
        background-color: white; 
        border: none;
        z-index: 9999; 
        padding: 15px; 
        border-radius: 10px; 
        font-family: Arial, sans-serif;
        box-shadow: 0 2px 15px rgba(0,0,0,0.1);">
        
        <div style="font-weight: bold; font-size: 16px; margin-bottom: 12px; color: #202124; border-bottom: 2px solid #1a73e8; padding-bottom: 8px;">Route Legend</div>
        
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="background: #0b8043; width: 30px; height: 4px; display: inline-block; margin-right: 10px; border-radius: 2px;"></div>
            <div style="display: inline-block; color: #3c4043;">Optimized Road Path</div>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="background: #d93025; width: 30px; height: 4px; display: inline-block; margin-right: 10px; border-radius: 2px; border-top: 1px solid transparent; border-bottom: 1px solid transparent; background-image: repeating-linear-gradient(to right, #d93025, #d93025 5px, transparent 5px, transparent 10px);"></div>
            <div style="display: inline-block; color: #3c4043;">Estimated Path (No Road Data)</div>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="color: #1a73e8; font-size: 18px; margin-right: 10px; width: 30px; display: flex; justify-content: center;">
                <i class="fa fa-building"></i>
            </div>
            <div style="display: inline-block; color: #3c4043;">Delivery Stop</div>
        </div>
        
        <div style="display: flex; align-items: center;">
            <div style="color: #ea4335; font-size: 18px; margin-right: 10px; width: 30px; display: flex; justify-content: center;">
                <i class="fa fa-home"></i>
            </div>
            <div style="display: inline-block; color: #3c4043;">Warehouse</div>
        </div>
        
        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #e8eaed; font-size: 12px; color: #5f6368; text-align: center;">
            Click on route segments or markers for details
        </div>
    </div>
    '''
    route_map.get_root().html.add_child(folium.Element(legend_html))
    
    # Add Font Awesome for better icons
    route_map.get_root().header.add_child(folium.Element('''
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
    '''))
    
    # Add responsive design
    route_map.get_root().header.add_child(folium.Element('''
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body {
                margin: 0;
                padding: 0;
                font-family: Arial, sans-serif;
            }
            
            .folium-map {
                position: absolute;
                width: 100%;
                height: 100%;
                left: 0;
                top: 0;
            }
            
            /* Responsive styles for smaller screens */
            @media screen and (max-width: 768px) {
                #sidebar {
                    width: 280px !important;
                }
                
                #mapLegend {
                    bottom: 10px !important;
                    right: 10px !important;
                    width: 200px !important;
                    font-size: 12px !important;
                }
                
                .leaflet-popup-content {
                    max-width: 220px !important;
                }
            }
            
            /* Very small screens (mobile) */
            @media screen and (max-width: 480px) {
                #sidebar {
                    width: 250px !important;
                }
                
                #mapLegend {
                    bottom: 5px !important;
                    right: 5px !important;
                    width: 180px !important;
                    padding: 10px !important;
                }
                
                .leaflet-popup-content {
                    max-width: 180px !important;
                }
            }
            
            /* Improve scrollbar appearance */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            
            ::-webkit-scrollbar-track {
                background: #f1f3f4;
                border-radius: 10px;
            }
            
            ::-webkit-scrollbar-thumb {
                background: #dadce0;
                border-radius: 10px;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: #1a73e8;
            }
            
            /* Smooth transitions for UI elements */
            #sidebar, .leaflet-control, .leaflet-popup, #mapLegend {
                transition: all 0.3s ease;
            }
            
            /* Improve layer control appearance */
            .leaflet-control-layers {
                border-radius: 8px !important;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1) !important;
                overflow: hidden !important;
            }
            
            .leaflet-control-layers-toggle {
                width: 36px !important;
                height: 36px !important;
                background-size: 20px 20px !important;
            }
            
            .leaflet-control-layers-expanded {
                padding: 10px !important;
                background-color: white !important;
                color: #3c4043 !important;
                font-family: Arial, sans-serif !important;
            }
            
            /* Improve popup appearance */
            .leaflet-popup-content-wrapper {
                border-radius: 10px !important;
                box-shadow: 0 3px 14px rgba(0,0,0,0.2) !important;
            }
            
            .leaflet-popup-tip {
                box-shadow: 0 3px 14px rgba(0,0,0,0.2) !important;
            }
        </style>
    '''))
    
    # Prepare route data for the interactive sidebar
    route_data = []
    for i, idx in enumerate(best_order):
        stop_info = {
            "id": idx,
            "order": i,
            "label": df.iloc[idx]['Label'],
            "address": df.iloc[idx]['Address'],
            "coords": df.iloc[idx]['Coords']
        }
        
        # Add travel info for segments (except the last stop)
        if i < len(best_order) - 1:
            next_idx = best_order[i+1]
            duration_min = duration_matrix[idx, next_idx] / 60  # Convert to minutes
            distance_km = distance_matrix[idx, next_idx] / 1000  # Convert to km
            
            stop_info["next_stop_id"] = next_idx
            stop_info["duration_to_next"] = duration_min
            stop_info["distance_to_next"] = distance_km
        
        route_data.append(stop_info)
    
    # Convert route_geometries to a format suitable for JavaScript
    js_geometries = {}
    for key, coords in route_geometries.items():
        # Convert tuple key to string key
        js_geometries[f"{key[0]},{key[1]}"] = coords
    
    # Create JavaScript for the interactive sidebar
    add_interactive_sidebar(route_map, route_data, js_geometries, total_km, total_hours)
    
    return route_map

def add_interactive_sidebar(route_map, route_data, geometries, total_km, total_hours):
    """Add an interactive sidebar to the map"""
    # Convert data to JSON for JavaScript
    route_json = json.dumps(route_data)
    geometries_json = json.dumps(geometries)
    
    # Initialize delivery progress data
    delivery_progress = {
        "completed": 0,
        "total": len(route_data) - 1  # Exclude warehouse
    }
    delivery_progress_json = json.dumps(delivery_progress)
    
    # Create the sidebar HTML/JavaScript
    sidebar_html = f"""
    <script>
        // Route data from Python
        var routeData = {route_json};
        
        // Route geometries data
        var routeGeometries = {geometries_json};
        
        // Initialize delivery progress
        var deliveryProgress = {delivery_progress_json};
        
        // Function to create the sidebar
        function createSidebar() {{
            var sidebar = document.createElement('div');
            sidebar.id = 'sidebar';
            sidebar.style.position = 'absolute';
            sidebar.style.top = '10px';
            sidebar.style.left = '10px';
            sidebar.style.width = '320px';
            sidebar.style.maxHeight = '90%';
            sidebar.style.overflowY = 'auto';
            sidebar.style.backgroundColor = 'white';
            sidebar.style.padding = '20px';
            sidebar.style.borderRadius = '12px';
            sidebar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.15)';
            sidebar.style.zIndex = '1000';
            sidebar.style.fontFamily = 'Arial, sans-serif';
            
            // Add header with improved styling
            var header = document.createElement('div');
            header.style.marginBottom = '25px';
            header.innerHTML = `
                <h2 style="margin: 0 0 15px 0; color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 12px; font-size: 24px;">
                    Delivery Route Planner
                </h2>
                <div style="display: flex; align-items: center; gap: 15px;">
                    <div style="flex: 1;">
                        <div style="font-size: 0.9em; color: #5f6368; margin-bottom: 4px;">Today's Progress</div>
                        <div style="font-size: 1.3em; font-weight: bold; color: #202124;">
                            ${{deliveryProgress.completed}}/${{deliveryProgress.total}} Stops
                        </div>
                    </div>
                    <div style="flex: 1;">
                        <div style="font-size: 0.9em; color: #5f6368; margin-bottom: 4px;">Estimated Time</div>
                        <div style="font-size: 1.3em; font-weight: bold; color: #202124;">
                            {total_hours:.1f} hours
                        </div>
                    </div>
                </div>
            `;
            sidebar.appendChild(header);
            
            // Add progress bar
            var progressBar = document.createElement('div');
            progressBar.style.height = '10px';
            progressBar.style.backgroundColor = '#e8eaed';
            progressBar.style.borderRadius = '5px';
            progressBar.style.marginBottom = '25px';
            progressBar.style.overflow = 'hidden';
            
            var progressFill = document.createElement('div');
            progressFill.id = 'progress-fill';
            progressFill.style.height = '100%';
            progressFill.style.width = '0%';
            progressFill.style.backgroundColor = '#1a73e8';
            progressFill.style.transition = 'width 0.3s ease';
            
            progressBar.appendChild(progressFill);
            sidebar.appendChild(progressBar);
            
            // Add Quick Tips section
            var aboutSection = document.createElement('div');
            aboutSection.style.marginBottom = '25px';
            aboutSection.style.padding = '18px';
            aboutSection.style.backgroundColor = '#f8f9fa';
            aboutSection.style.borderRadius = '10px';
            aboutSection.style.border = '1px solid #e9ecef';
            aboutSection.innerHTML = `
                <h3 style="margin: 0 0 12px 0; color: #1a73e8; font-size: 18px;">Quick Tips</h3>
                <ul style="margin: 0; padding-left: 20px; color: #3c4043; line-height: 1.5;">
                    <li>Click on stops to mark them as completed</li>
                    <li>Track your delivery progress with the progress bar</li>
                    <li>Check estimated distance and time for each leg</li>
                    <li>Use the map to visualize your optimized route</li>
                </ul>
            `;
            sidebar.appendChild(aboutSection);
            
            // Add route info section (previously used in "Plan Next Delivery")
            var routeInfo = document.createElement('div');
            routeInfo.id = 'route-info';
            routeInfo.style.marginBottom = '25px';
            routeInfo.style.padding = '18px';
            routeInfo.style.backgroundColor = '#e8f4fc';
            routeInfo.style.borderRadius = '10px';
            routeInfo.style.display = 'none';
            routeInfo.style.border = '1px solid #c2e7ff';
            sidebar.appendChild(routeInfo);
            
            // Add reset button
            var resetButton = document.createElement('button');
            resetButton.id = 'reset-button';
            resetButton.innerHTML = 'Reset Selection';
            resetButton.style.width = '100%';
            resetButton.style.padding = '12px';
            resetButton.style.backgroundColor = '#ea4335';
            resetButton.style.color = 'white';
            resetButton.style.border = 'none';
            resetButton.style.borderRadius = '6px';
            resetButton.style.cursor = 'pointer';
            resetButton.style.fontWeight = 'bold';
            resetButton.style.display = 'none';
            resetButton.style.marginBottom = '25px';
            resetButton.style.boxShadow = '0 2px 6px rgba(0,0,0,0.1)';
            sidebar.appendChild(resetButton);
            
            // Add stops list section
            var stopsHeader = document.createElement('div');
            stopsHeader.style.marginBottom = '15px';
            stopsHeader.innerHTML = `
                <h3 style="margin: 0; color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; font-size: 18px;">
                    Delivery Stops
                </h3>
                <div style="display: flex; justify-content: space-between; margin-top: 10px; color: #5f6368; font-size: 0.9em;">
                    <span>Click to mark as completed</span>
                    <span id="completed-count">0/${{deliveryProgress.total}}</span>
                </div>
            `;
            sidebar.appendChild(stopsHeader);
            
            var stopsList = document.createElement('ol');
            stopsList.id = 'stops-list';
            stopsList.style.paddingLeft = '20px';
            stopsList.style.marginTop = '15px';
            
            // Populate the list with improved styling
            routeData.forEach(function(stop) {{
                var item = document.createElement('li');
                item.id = 'stop-item-' + stop.id;
                item.style.marginBottom = '15px';
                item.style.padding = '15px';
                item.style.borderRadius = '10px';
                item.style.backgroundColor = '#f8f9fa';
                item.style.cursor = 'pointer';
                item.style.transition = 'all 0.2s ease';
                item.style.border = '1px solid #e9ecef';
                item.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
                
                // Extract stop number and location name
                var stopNumber = stop.label.replace(/\D/g, '');
                var locationName = stop.label.split(':')[1] || stop.address.split(',')[0];
                locationName = locationName.trim();
                
                item.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 1; margin-right: 15px;">
                            <strong style="color: #202124; font-size: 16px;">Stop #${{stopNumber}}: ${{locationName}}</strong>
                            <div style="color: #5f6368; font-size: 0.9em; margin-top: 6px;">${{stop.address}}</div>
                        </div>
                        <div class="completion-indicator" style="width: 24px; height: 24px; min-width: 24px; border-radius: 50%; border: 2px solid #bdc3c7; background-color: white; flex-shrink: 0; transition: all 0.2s ease;"></div>
                    </div>
                `;
                
                if(stop.hasOwnProperty('distance_to_next')) {{
                    item.innerHTML += `
                        <div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid #e9ecef;">
                            <div style="display: flex; justify-content: space-between;">
                                <small style="color: #1a73e8; font-weight: bold;">
                                    ${{stop.distance_to_next.toFixed(1)}} km
                                </small>
                                <small style="color: #1a73e8; font-weight: bold;">
                                    ${{stop.duration_to_next.toFixed(0)}} min
                                </small>
                            </div>
                        </div>
                    `;
                }}
                
                // Add hover effect
                item.onmouseover = function() {{
                    this.style.backgroundColor = '#f1f3f4';
                    this.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
                }};
                
                item.onmouseout = function() {{
                    if(!this.classList.contains('completed')) {{
                        this.style.backgroundColor = '#f8f9fa';
                        this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
                    }}
                }};
                
                // Add click handler for completion
                item.onclick = function() {{
                    if(!this.classList.contains('completed')) {{
                        this.classList.add('completed');
                        this.style.backgroundColor = '#e6f4ea';
                        this.style.border = '1px solid #34a853';
                        this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
                        var indicator = this.querySelector('.completion-indicator');
                        indicator.style.backgroundColor = '#34a853';
                        indicator.style.border = '2px solid #34a853';
                        
                        deliveryProgress.completed++;
                        updateProgress();
                    }} else {{
                        this.classList.remove('completed');
                        this.style.backgroundColor = '#f8f9fa';
                        this.style.border = '1px solid #e9ecef';
                        this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
                        var indicator = this.querySelector('.completion-indicator');
                        indicator.style.backgroundColor = 'white';
                        indicator.style.border = '2px solid #bdc3c7';
                        
                        deliveryProgress.completed--;
                        updateProgress();
                    }}
                }};
                
                stopsList.appendChild(item);
            }});
            
            sidebar.appendChild(stopsList);
            
            // Add total distance and time
            var totalInfo = document.createElement('div');
            totalInfo.style.marginTop = '25px';
            totalInfo.style.padding = '18px';
            totalInfo.style.backgroundColor = '#e6f4ea';
            totalInfo.style.borderRadius = '10px';
            totalInfo.style.fontWeight = 'bold';
            totalInfo.style.color = '#202124';
            totalInfo.style.border = '1px solid #ceead6';
            totalInfo.innerHTML = `
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-size: 0.9em; color: #5f6368; margin-bottom: 4px;">Total Distance</div>
                        <div style="font-size: 1.3em;">{total_km:.1f} km</div>
                    </div>
                    <div>
                        <div style="font-size: 0.9em; color: #5f6368; margin-bottom: 4px;">Total Time</div>
                        <div style="font-size: 1.3em;">{total_hours:.1f} hours</div>
                    </div>
                </div>
            `;
            sidebar.appendChild(totalInfo);
            
            // Add a toggle button for the sidebar
            var toggleButton = document.createElement('button');
            toggleButton.innerHTML = '&laquo;';
            toggleButton.style.position = 'absolute';
            toggleButton.style.right = '-36px';
            toggleButton.style.top = '10px';
            toggleButton.style.backgroundColor = '#1a73e8';
            toggleButton.style.color = 'white';
            toggleButton.style.border = 'none';
            toggleButton.style.borderRadius = '0 6px 6px 0';
            toggleButton.style.padding = '10px 14px';
            toggleButton.style.cursor = 'pointer';
            toggleButton.style.fontSize = '16px';
            toggleButton.style.boxShadow = '2px 0 8px rgba(0,0,0,0.1)';
            toggleButton.onclick = function() {{
                if(sidebar.style.left === '10px') {{
                    sidebar.style.left = '-330px';
                    toggleButton.innerHTML = '&raquo;';
                }} else {{
                    sidebar.style.left = '10px';
                    toggleButton.innerHTML = '&laquo;';
                }}
            }};
            sidebar.appendChild(toggleButton);
            
            return sidebar;
        }}
        
        // Function to update progress
        function updateProgress() {{
            var progressFill = document.getElementById('progress-fill');
            var completedCount = document.getElementById('completed-count');
            var progress = (deliveryProgress.completed / deliveryProgress.total) * 100;
            
            progressFill.style.width = progress + '%';
            completedCount.textContent = deliveryProgress.completed + '/' + deliveryProgress.total;
            
            // Update header progress
            var header = document.querySelector('#sidebar > div:first-child');
            header.querySelector('div:nth-child(2) > div:nth-child(2)').textContent = 
                deliveryProgress.completed + '/' + deliveryProgress.total + ' Stops';
        }}
        
        // Function to reset the route selection
        function resetRouteSelection() {{
            // Hide route info and reset button
            document.getElementById('route-info').style.display = 'none';
            document.getElementById('reset-button').style.display = 'none';
            
            // Clear the custom route group
            if (window.custom_route_group) {{
                window.custom_route_group.clearLayers();
            }}
            
            // Show the optimized route group
            if (window.optimized_route_group) {{
                window.map.addLayer(window.optimized_route_group);
            }}
        }}
        
        // Initialize the sidebar when the document is ready
        document.addEventListener('DOMContentLoaded', function() {{
            // Create and append the sidebar
            var sidebar = createSidebar();
            document.body.appendChild(sidebar);
            
            // Add event listener for the reset button
            document.getElementById('reset-button').addEventListener('click', resetRouteSelection);
            
            // Initialize progress
            updateProgress();
        }});
    </script>
    """
    
    # Add the sidebar HTML to the map
    route_map.get_root().html.add_child(folium.Element(sidebar_html))

# Main script execution
if __name__ == "__main__":
    # Load addresses
    print("Loading addresses...")
    addresses = []

    try:
        # Read CSV file and process each line
        with open("addresses.csv", "r") as f:
            for line in f:
                parts = line.strip().split(',', 1)  # Split only on first comma
                if len(parts) >= 2:
                    label = parts[0]
                    address = parts[1].strip()
                    addresses.append((label, address))
    except Exception as e:
        print(f"Error reading addresses.csv: {e}")
        exit(1)

    if not addresses:
        print("No addresses found in the CSV file.")
        exit(1)

    # Create DataFrame
    df = pd.DataFrame(addresses, columns=['Label', 'Address'])

    # Geocode addresses
    print("Geocoding addresses with MapQuest API...")
    coords = []
    for address in tqdm(df['Address']):
        coord = geocode_address(address)
        coords.append(coord)
        time.sleep(0.5)  # Rate limiting to avoid API issues

    df['Coords'] = coords

    # Remove entries with failed geocoding
    valid_entries = df['Coords'].notnull()
    if not all(valid_entries):
        print(f"Warning: {sum(~valid_entries)} addresses could not be geocoded and will be skipped.")
        df = df[valid_entries].reset_index(drop=True)

    if len(df) <= 1:
        print("Not enough valid addresses to calculate a route.")
        exit(1)

    # Store the warehouse coordinates
    warehouse = df.iloc[0]
    warehouse_coords = warehouse["Coords"]
    delivery_stops = df.iloc[1:]

    # Create distance matrix between all points
    print("Building distance matrix using OSRM API...")
    n = len(df)
    distance_matrix = np.zeros((n, n))
    duration_matrix = np.zeros((n, n))
    route_geometries = {}  # Store route geometries between points

    for i in tqdm(range(n)):
        for j in range(n):
            if i != j:
                duration, distance, geometry = get_route_with_geometry(df.iloc[i]["Coords"], df.iloc[j]["Coords"])
                distance_matrix[i, j] = distance
                duration_matrix[i, j] = duration
                
                # Store the geometry for this route
                if geometry:
                    route_geometries[(i, j)] = geometry
                
                time.sleep(0.3)  # Rate limiting for API

    # For larger problems, simplify to reduce computation time
    print("Finding optimal route...")
    if n <= 8:  # Only use brute force for very small problems
        locations = list(range(1, n))  # Skip warehouse (index 0)
        warehouse_idx = 0
        best_order = None
        best_distance = float("inf")
        
        for perm in tqdm(list(permutations(locations))):
            route = [warehouse_idx] + list(perm) + [warehouse_idx]
            distance = sum(distance_matrix[route[i], route[i+1]] for i in range(len(route)-1))
            if distance < best_distance:
                best_distance = distance
                best_order = route
    else:
        # Use nearest neighbor for larger problems (standard approach for delivery routing)
        print("Using nearest neighbor algorithm for route optimization...")
        warehouse_idx = 0
        current = warehouse_idx
        unvisited = set(range(1, n))  # All stops except warehouse
        route = [current]
        
        while unvisited:
            next_stop = min(unvisited, key=lambda x: distance_matrix[current, x])
            route.append(next_stop)
            unvisited.remove(next_stop)
            current = next_stop
        
        route.append(warehouse_idx)  # Return to warehouse
        best_order = route
        best_distance = sum(distance_matrix[route[i], route[i+1]] for i in range(len(route)-1))

    # Print results
    print("\nRoute Summary:")
    total_hours = sum(duration_matrix[best_order[i], best_order[i+1]] for i in range(len(best_order)-1)) / 3600
    total_km = best_distance / 1000

    print(f"Optimal route found!")
    print(f"Total distance: {total_km:.2f} km")
    print(f"Total estimated time: {total_hours:.2f} hours")
    print("\nRoute order:")
    for i, idx in enumerate(best_order):
        if i == 0 or i == len(best_order) - 1:
            print(f"  {i}. {df.iloc[idx]['Label']} (Warehouse): {df.iloc[idx]['Address']}")
        else:
            print(f"  {i}. {df.iloc[idx]['Label']}: {df.iloc[idx]['Address']}")

    # Create the interactive map with the route visualization
    print("\nCreating interactive map visualization with actual road paths...")
    route_map = create_interactive_map(df, best_order, route_geometries, distance_matrix, duration_matrix, total_km, total_hours)

    # Save map
    route_map.save('route_map.html')
    print("Interactive route map saved as 'route_map.html'")
    print("\nOpen route_map.html in your web browser to view the optimized route with actual road paths and interactive sidebar.")