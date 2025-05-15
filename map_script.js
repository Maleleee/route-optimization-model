// Store map instance globally
var mapInstance = null;

// Function to get the map instance
function getMap() {
    if (mapInstance) return mapInstance;
    
    // Try to get the map from the DOM
    var mapElement = document.querySelector('.folium-map');
    if (!mapElement) return null;
    
    // Get the Leaflet map instance
    var mapId = mapElement.id;
    var map = L.DomUtil.get(mapId)._leaflet_map;
    
    if (map) {
        mapInstance = map;
        return map;
    }
    
    return null;
}

// Function to initialize the map
function initializeMap() {
    var map = getMap();
    if (!map) {
        console.log('Waiting for map initialization...');
        setTimeout(initializeMap, 100);
        return;
    }
    console.log('Map initialized successfully');
}

// Function to display a custom route
function displayCustomRoute() {
    var map = getMap();
    if (!map) {
        console.error('Map not initialized yet. Please wait a moment and try again.');
        return;
    }

    var startId = parseInt(document.getElementById('start-select').value);
    var endId = parseInt(document.getElementById('end-select').value);
    
    if(isNaN(startId) || isNaN(endId) || startId === endId) {
        return;
    }
    
    // Get the selected locations
    var startStop = routeData.find(stop => stop.id === startId);
    var endStop = routeData.find(stop => stop.id === endId);
    
    if(!startStop || !endStop) {
        console.error('Could not find selected stops:', { startId: startId, endId: endId });
        return;
    }
    
    // Show the reset button and hide the show route button
    document.getElementById('reset-button').style.display = 'block';
    document.getElementById('show-route-button').style.display = 'none';
    
    // Create custom route using direct polyline creation
    var routeKey = startId + ',' + endId;
    var geometry = routeGeometries[routeKey];
    
    // Remove any existing custom route
    var existingRoute = document.querySelector('.custom-route');
    if (existingRoute) {
        existingRoute.remove();
    }
    
    // Create a new polyline
    var polyline;
    if(geometry) {
        polyline = L.polyline(
            geometry,
            {
                color: '#FF3D00',
                weight: 6,
                opacity: 0.9,
                className: 'custom-route'
            }
        );
    } else {
        polyline = L.polyline(
            [startStop.coords, endStop.coords],
            {
                color: '#FF3D00',
                weight: 6,
                opacity: 0.9,
                dashArray: '10, 10',
                className: 'custom-route'
            }
        );
    }
    
    // Add the polyline to the map
    polyline.addTo(map);
    
    // Add markers for start and end points
    var startMarker = L.circleMarker(startStop.coords, {
        radius: 14,
        fillColor: '#1E88E5',
        color: '#000',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9,
        className: 'custom-route'
    }).addTo(map);
    
    var endMarker = L.circleMarker(endStop.coords, {
        radius: 14,
        fillColor: '#43A047',
        color: '#000',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9,
        className: 'custom-route'
    }).addTo(map);
    
    // Update route info
    var routeInfo = document.getElementById('route-info');
    routeInfo.style.display = 'block';
    
    // Calculate direct distance and duration if available
    var directDistance = null;
    var directDuration = null;
    
    routeData.forEach(function(stop) {
        if(stop.id === startId && stop.next_stop_id === endId) {
            directDistance = stop.distance_to_next;
            directDuration = stop.duration_to_next;
        }
    });
    
    // Extract location names
    var startLocationName = startStop.label.split(':')[1] || startStop.address.split(',')[0];
    var endLocationName = endStop.label.split(':')[1] || endStop.address.split(',')[0];
    startLocationName = startLocationName.trim();
    endLocationName = endLocationName.trim();
    
    // Create route info HTML
    var infoHtml = '<div style="margin-bottom: 10px;">' +
        '<div style="color: #2c3e50; font-weight: bold; margin-bottom: 5px;">From:</div>' +
        '<div style="color: #34495e;">' + startLocationName + '</div>' +
        '<div style="color: #7f8c8d; font-size: 0.9em;">' + startStop.address + '</div>' +
        '</div>' +
        '<div style="margin-bottom: 10px;">' +
        '<div style="color: #2c3e50; font-weight: bold; margin-bottom: 5px;">To:</div>' +
        '<div style="color: #34495e;">' + endLocationName + '</div>' +
        '<div style="color: #7f8c8d; font-size: 0.9em;">' + endStop.address + '</div>' +
        '</div>';
    
    if(directDistance !== null && directDuration !== null) {
        infoHtml += '<div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e9ecef;">' +
            '<div style="display: flex; justify-content: space-between;">' +
            '<div>' +
            '<div style="color: #2c3e50; font-weight: bold;">Distance</div>' +
            '<div style="color: #34495e;">' + directDistance.toFixed(1) + ' km</div>' +
            '</div>' +
            '<div>' +
            '<div style="color: #2c3e50; font-weight: bold;">Est. Time</div>' +
            '<div style="color: #34495e;">' + directDuration.toFixed(0) + ' min</div>' +
            '</div>' +
            '</div>' +
            '</div>';
    } else {
        infoHtml += '<div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e9ecef;">' +
            '<div style="color: #7f8c8d; font-style: italic;">' +
            'Direct route information not available.' +
            '</div>' +
            '</div>';
    }
    
    routeInfo.innerHTML = infoHtml;
    
    // Hide the optimized route
    var optimizedRoute = document.querySelector('.folium-map path');
    if (optimizedRoute) {
        optimizedRoute.style.display = 'none';
    }
    
    // Fit the map to show the route
    var bounds = polyline.getBounds();
    map.fitBounds(bounds, {
        padding: [50, 50]
    });
}

// Function to reset the route selection
function resetRouteSelection() {
    var map = getMap();
    if (!map) {
        console.error('Map not initialized yet. Please wait a moment and try again.');
        return;
    }

    // Clear dropdowns
    document.getElementById('start-select').value = '';
    document.getElementById('end-select').value = '';
    
    // Hide route info, reset button and show route button
    document.getElementById('route-info').style.display = 'none';
    document.getElementById('reset-button').style.display = 'none';
    document.getElementById('show-route-button').style.display = 'none';
    
    // Remove custom route elements
    var customElements = document.querySelectorAll('.custom-route');
    customElements.forEach(function(element) {
        element.remove();
    });
    
    // Show the optimized route
    var optimizedRoute = document.querySelector('.folium-map path');
    if (optimizedRoute) {
        optimizedRoute.style.display = '';
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Document ready, initializing map...');
    initializeMap();
});

// Also try to initialize when the window is loaded
window.addEventListener('load', function() {
    console.log('Window loaded, checking map initialization...');
    initializeMap();
}); 