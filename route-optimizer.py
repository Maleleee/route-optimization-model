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
    
    # Create the map
    route_map = folium.Map(location=map_center, zoom_start=11)
    
    # Add markers for all locations
    for i, row in df.iterrows():
        if i == 0:  # Warehouse
            icon = folium.Icon(color='red', icon='home')
        else:
            icon = folium.Icon(color='blue', icon='info-sign')
        
        popup_text = f"{row['Label']}: {row['Address']}"
        folium.Marker(
            location=row["Coords"],
            popup=popup_text,
            icon=icon,
            tooltip=row['Label']
        ).add_to(route_map)
    
    # Create a FeatureGroup for the optimized route
    optimized_route_group = folium.FeatureGroup(name="Optimized Route")
    
    # Add route lines with actual road geometry
    for i in range(len(best_order) - 1):
        start_idx = best_order[i]
        end_idx = best_order[i + 1]
        
        # Get the route geometry between these points
        route_key = (start_idx, end_idx)
        if route_key in route_geometries and route_geometries[route_key]:
            path = route_geometries[route_key]
            
            # Add the actual road path
            folium.PolyLine(
                locations=path,
                color='green',
                weight=4,
                opacity=0.8,
                popup=f"Leg {i+1}: {df.iloc[start_idx]['Label']} to {df.iloc[end_idx]['Label']}",
                tooltip=f"Leg {i+1}: {df.iloc[start_idx]['Label']} → {df.iloc[end_idx]['Label']}"
            ).add_to(optimized_route_group)
        else:
            # Fallback to straight line if no geometry available
            start_coords = df.iloc[start_idx]["Coords"]
            end_coords = df.iloc[end_idx]["Coords"]
            
            folium.PolyLine(
                locations=[start_coords, end_coords],
                color='red',  # Use red to indicate missing road data
                weight=2,
                opacity=0.7,
                popup=f"Leg {i+1}: {df.iloc[start_idx]['Label']} to {df.iloc[end_idx]['Label']} (no road data)",
                tooltip=f"Leg {i+1}: {df.iloc[start_idx]['Label']} → {df.iloc[end_idx]['Label']}"
            ).add_to(optimized_route_group)
        
        # Add a marker for the route number
        mid_point = df.iloc[end_idx]["Coords"]
        folium.Marker(
            location=mid_point,
            icon=folium.DivIcon(html=f"<div style='font-size:10pt;color:black;font-weight:bold;background-color:white;border-radius:50%;padding:3px;border:2px solid green'>{i+1}</div>"),
        ).add_to(optimized_route_group)
    
    optimized_route_group.add_to(route_map)
    
    # Add an improved legend with better styling
    legend_html = '''
    <div id="mapLegend" style="position: fixed; 
                bottom: 50px; right: 50px; width: 220px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                padding: 10px; border-radius: 5px; font-family: Arial, sans-serif;">
        <div style="font-weight: bold; font-size: 14px; margin-bottom: 8px;">Route Legend</div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <div style="background: green; width: 15px; height: 3px; display: inline-block; margin-right: 5px;"></div>
            <div style="display: inline-block;">Actual Road Path</div>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <div style="background: red; width: 15px; height: 3px; display: inline-block; margin-right: 5px;"></div>
            <div style="display: inline-block;">Straight Path (Missing Road Data)</div>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <div style="color: blue; font-size: 15px; margin-right: 5px;">&#9679;</div>
            <div style="display: inline-block;">Delivery Stop</div>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="color: red; font-size: 15px; margin-right: 5px;">&#9679;</div>
            <div style="display: inline-block;">Warehouse</div>
        </div>
    </div>
    '''
    route_map.get_root().html.add_child(folium.Element(legend_html))
    
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
        js_geometries[f"{key[0]},{key[1]}"] = coords
    
    # Create JavaScript for the interactive sidebar
    add_interactive_sidebar(route_map, route_data, js_geometries, total_km, total_hours)
    
    return route_map

def add_interactive_sidebar(route_map, route_data, geometries, total_km, total_hours):
    """Add an interactive sidebar to the map"""
    # Convert data to JSON for JavaScript
    route_json = json.dumps(route_data)
    geometries_json = json.dumps(geometries)
    
    # Create the sidebar HTML/JavaScript
    sidebar_html = f"""
    <script>
        // Route data from Python
        var routeData = {route_json};
        
        // Route geometries data
        var routeGeometries = {geometries_json};
        
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
            sidebar.style.padding = '10px';
            sidebar.style.borderRadius = '5px';
            sidebar.style.boxShadow = '0 0 10px rgba(0,0,0,0.5)';
            sidebar.style.zIndex = '1000';
            
            var header = document.createElement('h3');
            header.innerHTML = 'Route Planner';
            sidebar.appendChild(header);
            
            var description = document.createElement('p');
            description.innerHTML = 'Select start and end locations to display a custom route.';
            sidebar.appendChild(description);
            
            // Create start point dropdown
            var startLabel = document.createElement('label');
            startLabel.innerHTML = 'Start Point: ';
            startLabel.style.display = 'block';
            startLabel.style.marginTop = '10px';
            startLabel.style.fontWeight = 'bold';
            sidebar.appendChild(startLabel);
            
            var startSelect = document.createElement('select');
            startSelect.id = 'start-select';
            startSelect.style.width = '100%';
            startSelect.style.marginBottom = '10px';
            startSelect.style.padding = '5px';
            sidebar.appendChild(startSelect);
            
            // Create end point dropdown
            var endLabel = document.createElement('label');
            endLabel.innerHTML = 'End Point: ';
            endLabel.style.display = 'block';
            endLabel.style.marginTop = '10px';
            endLabel.style.fontWeight = 'bold';
            sidebar.appendChild(endLabel);
            
            var endSelect = document.createElement('select');
            endSelect.id = 'end-select';
            endSelect.style.width = '100%';
            endSelect.style.marginBottom = '10px';
            endSelect.style.padding = '5px';
            sidebar.appendChild(endSelect);
            
            // Add route info section
            var routeInfo = document.createElement('div');
            routeInfo.id = 'route-info';
            routeInfo.style.marginTop = '20px';
            routeInfo.style.padding = '10px';
            routeInfo.style.backgroundColor = '#f8f8f8';
            routeInfo.style.borderRadius = '5px';
            routeInfo.style.display = 'none';
            sidebar.appendChild(routeInfo);
            
            // Add reset button
            var resetButton = document.createElement('button');
            resetButton.id = 'reset-button';
            resetButton.innerHTML = 'Reset Selection';
            resetButton.style.marginTop = '15px';
            resetButton.style.padding = '8px 15px';
            resetButton.style.backgroundColor = '#dc3545';
            resetButton.style.color = 'white';
            resetButton.style.border = 'none';
            resetButton.style.borderRadius = '4px';
            resetButton.style.cursor = 'pointer';
            resetButton.style.display = 'none';  // Initially hidden
            resetButton.style.width = '100%';
            sidebar.appendChild(resetButton);
            
            // Add a toggle button for the sidebar
            var toggleButton = document.createElement('button');
            toggleButton.innerHTML = '&laquo;';
            toggleButton.style.position = 'absolute';
            toggleButton.style.right = '10px';
            toggleButton.style.top = '10px';
            toggleButton.style.backgroundColor = '#007bff';
            toggleButton.style.color = 'white';
            toggleButton.style.border = 'none';
            toggleButton.style.borderRadius = '5px';
            toggleButton.style.padding = '5px 10px';
            toggleButton.style.cursor = 'pointer';
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
            
            // Add stops list section
            var stopsHeader = document.createElement('h4');
            stopsHeader.innerHTML = 'Optimized Route';
            stopsHeader.style.marginTop = '20px';
            sidebar.appendChild(stopsHeader);
            
            var stopsList = document.createElement('ol');
            stopsList.id = 'stops-list';
            stopsList.style.paddingLeft = '20px';
            
            // Populate the list
            routeData.forEach(function(stop) {{
                var item = document.createElement('li');
                item.id = 'stop-item-' + stop.id;
                item.innerHTML = '<strong>' + stop.label + '</strong>: ' + stop.address;
                
                if(stop.hasOwnProperty('distance_to_next')) {{
                    item.innerHTML += '<br><small>Next: ' + stop.distance_to_next.toFixed(1) + 
                        ' km, ' + stop.duration_to_next.toFixed(0) + ' min</small>';
                }}
                
                stopsList.appendChild(item);
            }});
            
            sidebar.appendChild(stopsList);
            
            // Add total distance and time
            var totalInfo = document.createElement('div');
            totalInfo.style.marginTop = '15px';
            totalInfo.style.fontWeight = 'bold';
            totalInfo.innerHTML = 'Total Distance: {total_km:.1f} km<br>Total Time: {total_hours:.1f} hours';
            sidebar.appendChild(totalInfo);
            
            return sidebar;
        }}
        
        // Function to populate the dropdowns with stops in sequential order
        function populateDropdowns() {{
            var startSelect = document.getElementById('start-select');
            var endSelect = document.getElementById('end-select');
            
            // Add a default option
            var defaultStart = document.createElement('option');
            defaultStart.value = '';
            defaultStart.innerHTML = 'Select a starting point...';
            startSelect.appendChild(defaultStart);
            
            var defaultEnd = document.createElement('option');
            defaultEnd.value = '';
            defaultEnd.innerHTML = 'Select a destination...';
            endSelect.appendChild(defaultEnd);
            
            // First add the warehouse
            var warehouseStop = routeData.find(stop => stop.label.includes('Warehouse'));
            if (warehouseStop) {{
                var warehouseOption = document.createElement('option');
                warehouseOption.value = warehouseStop.id;
                warehouseOption.innerHTML = warehouseStop.label + ': ' + warehouseStop.address;
                
                startSelect.appendChild(warehouseOption.cloneNode(true));
                endSelect.appendChild(warehouseOption.cloneNode(true));
            }}
            
            // Sort stops by label name to get sequential order
            var sortedStops = [...routeData].filter(stop => !stop.label.includes('Warehouse'))
                .sort((a, b) => {{
                    // Extract numeric part from Stop labels (e.g., "Stop10" -> 10)
                    const aNum = parseInt(a.label.replace(/\D/g, '')) || 0;
                    const bNum = parseInt(b.label.replace(/\D/g, '')) || 0;
                    return aNum - bNum;
                }});
            
            // Add all locations to both dropdowns in sequential order
            sortedStops.forEach(function(stop) {{
                var startOption = document.createElement('option');
                startOption.value = stop.id;
                startOption.innerHTML = stop.label + ': ' + stop.address;
                startSelect.appendChild(startOption);
                
                var endOption = document.createElement('option');
                endOption.value = stop.id;
                endOption.innerHTML = stop.label + ': ' + stop.address;
                endSelect.appendChild(endOption);
            }});
        }}
        
        // Function to highlight stops in the list
        function highlightStops(startId, endId) {{
            // Reset all stops to normal styling
            routeData.forEach(function(stop) {{
                var item = document.getElementById('stop-item-' + stop.id);
                if (item) {{
                    item.style.backgroundColor = '';
                    item.style.padding = '';
                    item.style.borderRadius = '';
                }}
            }});
            
            // Highlight selected stops
            var startItem = document.getElementById('stop-item-' + startId);
            var endItem = document.getElementById('stop-item-' + endId);
            
            if (startItem) {{
                startItem.style.backgroundColor = '#e6f7ff';
                startItem.style.padding = '5px';
                startItem.style.borderRadius = '4px';
            }}
            
            if (endItem) {{
                endItem.style.backgroundColor = '#e6fff7';
                endItem.style.padding = '5px';
                endItem.style.borderRadius = '4px';
            }}
        }}
        
        // Function to reset the route selection
        function resetRouteSelection() {{
            // Clear dropdowns
            document.getElementById('start-select').value = '';
            document.getElementById('end-select').value = '';
            
            // Hide route info and reset button
            document.getElementById('route-info').style.display = 'none';
            document.getElementById('reset-button').style.display = 'none';
            
            // Remove custom route from map
            if(window.customRouteLayer) {{
                window.customRouteLayer.remove();
                window.customRouteLayer = null;
            }}
            
            // Remove custom markers
            if(window.startMarker) {{
                window.startMarker.remove();
                window.startMarker = null;
            }}
            
            if(window.endMarker) {{
                window.endMarker.remove();
                window.endMarker = null;
            }}
            
            // Reset highlighted stops
            routeData.forEach(function(stop) {{
                var item = document.getElementById('stop-item-' + stop.id);
                if (item) {{
                    item.style.backgroundColor = '';
                    item.style.padding = '';
                    item.style.borderRadius = '';
                }}
            }});
        }}
        
        // Function to display a custom route
        function displayCustomRoute() {{
            var startId = parseInt(document.getElementById('start-select').value);
            var endId = parseInt(document.getElementById('end-select').value);
            
            if(isNaN(startId) || isNaN(endId) || startId === endId) {{
                return;
            }}
            
            // Clear existing custom route and markers if any
            if(window.customRouteLayer) {{
                window.customRouteLayer.remove();
            }}
            
            if(window.startMarker) {{
                window.startMarker.remove();
            }}
            
            if(window.endMarker) {{
                window.endMarker.remove();
            }}
            
            // Create a new feature group for the custom route
            window.customRouteLayer = L.featureGroup();
            
            // Get the selected locations
            var startStop = routeData.find(stop => stop.id === startId);
            var endStop = routeData.find(stop => stop.id === endId);
            
            if(!startStop || !endStop) {{
                return;
            }}
            
            // Show the reset button
            document.getElementById('reset-button').style.display = 'block';
            
            // Add custom markers for the selected stops
            window.startMarker = L.circleMarker(startStop.coords, {{
                radius: 12,
                fillColor: '#4a89dc',
                color: '#000',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }}).addTo(map);
            
            window.endMarker = L.circleMarker(endStop.coords, {{
                radius: 12,
                fillColor: '#37bc9b',
                color: '#000',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }}).addTo(map);
            
            // Try to get the geometry for this route
            var routeKey = startId + ',' + endId;
            var geometry = routeGeometries[routeKey];
            
            if(geometry) {{
                // Add the actual road path
                L.polyLine(
                    geometry,
                    {{
                        color: '#ff6600',
                        weight: 6,
                        opacity: 0.9
                    }}
                ).addTo(window.customRouteLayer);
            }} else {{
                // Fallback to straight line
                L.polyLine(
                    [startStop.coords, endStop.coords],
                    {{
                        color: '#ff6600',
                        weight: 6,
                        opacity: 0.9,
                        dashArray: '10, 10'
                    }}
                ).addTo(window.customRouteLayer);
            }}
            
            // Add to map
            window.customRouteLayer.addTo(map);
            
            // Update route info
            var routeInfo = document.getElementById('route-info');
            routeInfo.style.display = 'block';
            
            // Calculate direct distance and duration if available
            var directDistance = null;
            var directDuration = null;
            
            routeData.forEach(function(stop) {{
                if(stop.id === startId && stop.next_stop_id === endId) {{
                    directDistance = stop.distance_to_next;
                    directDuration = stop.duration_to_next;
                }}
            }});
            
            var infoHtml = '<strong>From:</strong> ' + startStop.label + '<br>' +
                        '<strong>To:</strong> ' + endStop.label + '<br>';
            
            if(directDistance !== null && directDuration !== null) {{
                infoHtml += '<strong>Distance:</strong> ' + directDistance.toFixed(1) + ' km<br>' +
                        '<strong>Estimated Time:</strong> ' + directDuration.toFixed(0) + ' minutes';
            }} else {{
                infoHtml += '<em>Direct route information not available.</em>';
            }}
            
            routeInfo.innerHTML = infoHtml;
            
            // Highlight the selected stops in the list
            highlightStops(startId, endId);
        }}
    </script>

    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // Add the sidebar to the map
            document.body.appendChild(createSidebar());
            
            // Populate the dropdowns
            populateDropdowns();
            
            // Add event listeners
            document.getElementById('start-select').addEventListener('change', displayCustomRoute);
            document.getElementById('end-select').addEventListener('change', displayCustomRoute);
            document.getElementById('reset-button').addEventListener('click', resetRouteSelection);
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
