// Route data will be injected here by Python
var routeData = null;
var routeGeometries = null;
var totalDistance = 0;
var totalTime = 0;

// Function to create the sidebar
function createSidebar() {
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
    
    // Add "Show Route" button
    var showRouteButton = document.createElement('button');
    showRouteButton.id = 'show-route-button';
    showRouteButton.innerHTML = 'Show Route';
    showRouteButton.style.marginTop = '15px';
    showRouteButton.style.padding = '8px 15px';
    showRouteButton.style.backgroundColor = '#4CAF50';
    showRouteButton.style.color = 'white';
    showRouteButton.style.border = 'none';
    showRouteButton.style.borderRadius = '4px';
    showRouteButton.style.cursor = 'pointer';
    showRouteButton.style.width = '100%';
    showRouteButton.style.fontWeight = 'bold';
    showRouteButton.style.display = 'none'; // Initially hidden
    sidebar.appendChild(showRouteButton);
    
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
    toggleButton.onclick = function() {
        if(sidebar.style.left === '10px') {
            sidebar.style.left = '-330px';
            toggleButton.innerHTML = '&raquo;';
        } else {
            sidebar.style.left = '10px';
            toggleButton.innerHTML = '&laquo;';
        }
    };
    sidebar.appendChild(toggleButton);
    
    // Add a section explaining what the Optimized Route is
    var infoHeader = document.createElement('h4');
    infoHeader.innerHTML = 'About This Tool';
    infoHeader.style.marginTop = '20px';
    sidebar.appendChild(infoHeader);
    
    var infoText = document.createElement('p');
    infoText.style.fontSize = '12px';
    infoText.style.backgroundColor = '#f8f9fa';
    infoText.style.padding = '8px';
    infoText.style.borderRadius = '4px';
    infoText.innerHTML = 'The "Optimized Route" shows the most efficient delivery path that visits all stops while minimizing total distance and time. It starts and ends at the warehouse.';
    sidebar.appendChild(infoText);
    
    // Add stops list section with better heading
    var stopsHeader = document.createElement('h4');
    stopsHeader.innerHTML = 'Optimized Route Stops';
    stopsHeader.style.marginTop = '20px';
    sidebar.appendChild(stopsHeader);
    
    var stopsList = document.createElement('ol');
    stopsList.id = 'stops-list';
    stopsList.style.paddingLeft = '20px';
    
    // Populate the list
    routeData.forEach(function(stop) {
        var item = document.createElement('li');
        item.id = 'stop-item-' + stop.id;
        item.innerHTML = '<strong>' + stop.label + '</strong>: ' + stop.address;
        
        if(stop.hasOwnProperty('distance_to_next')) {
            item.innerHTML += '<br><small>Next: ' + stop.distance_to_next.toFixed(1) + 
                ' km, ' + stop.duration_to_next.toFixed(0) + ' min</small>';
        }
        
        stopsList.appendChild(item);
    });
    
    sidebar.appendChild(stopsList);
    
    // Add total distance and time
    var totalInfo = document.createElement('div');
    totalInfo.style.marginTop = '15px';
    totalInfo.style.fontWeight = 'bold';
    totalInfo.innerHTML = 'Total Distance: ' + totalDistance.toFixed(1) + ' km<br>Total Time: ' + totalTime.toFixed(1) + ' hours';
    sidebar.appendChild(totalInfo);
    
    return sidebar;
}

// Function to populate the dropdowns with stops in sequential order
function populateDropdowns() {
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
    if (warehouseStop) {
        var warehouseOption = document.createElement('option');
        warehouseOption.value = warehouseStop.id;
        warehouseOption.innerHTML = warehouseStop.label + ': ' + warehouseStop.address;
        
        startSelect.appendChild(warehouseOption.cloneNode(true));
        endSelect.appendChild(warehouseOption.cloneNode(true));
    }
    
    // Sort stops by label name to get sequential order
    var sortedStops = [...routeData].filter(stop => !stop.label.includes('Warehouse'))
        .sort((a, b) => {
            // Extract numeric part from Stop labels (e.g., "Stop10" -> 10)
            const aNum = parseInt(a.label.replace(/\D/g, '')) || 0;
            const bNum = parseInt(b.label.replace(/\D/g, '')) || 0;
            return aNum - bNum;
        });
    
    // Add all locations to both dropdowns in sequential order
    sortedStops.forEach(function(stop) {
        var startOption = document.createElement('option');
        startOption.value = stop.id;
        startOption.innerHTML = stop.label + ': ' + stop.address;
        startSelect.appendChild(startOption);
        
        var endOption = document.createElement('option');
        endOption.value = stop.id;
        endOption.innerHTML = stop.label + ': ' + stop.address;
        endSelect.appendChild(endOption);
    });
}

// Function to highlight stops in the list
function highlightStops(startId, endId) {
    // Reset all stops to normal styling
    routeData.forEach(function(stop) {
        var item = document.getElementById('stop-item-' + stop.id);
        if (item) {
            item.style.backgroundColor = '';
            item.style.padding = '';
            item.style.borderRadius = '';
        }
    });
    
    // Highlight selected stops
    var startItem = document.getElementById('stop-item-' + startId);
    var endItem = document.getElementById('stop-item-' + endId);
    
    if (startItem) {
        startItem.style.backgroundColor = '#e6f7ff';
        startItem.style.padding = '5px';
        startItem.style.borderRadius = '4px';
    }
    
    if (endItem) {
        endItem.style.backgroundColor = '#e6fff7';
        endItem.style.padding = '5px';
        endItem.style.borderRadius = '4px';
    }
}

// Function to check if both start and end points are selected
function checkSelections() {
    var startValue = document.getElementById('start-select').value;
    var endValue = document.getElementById('end-select').value;
    var showRouteButton = document.getElementById('show-route-button');
    
    // Show the button only if both selections are made and they're different
    if (startValue && endValue && startValue !== endValue) {
        showRouteButton.style.display = 'block';
    } else {
        showRouteButton.style.display = 'none';
    }
}

// Function to reset the route selection
function resetRouteSelection() {
    // Clear dropdowns
    document.getElementById('start-select').value = '';
    document.getElementById('end-select').value = '';
    
    // Hide route info, reset button and show route button
    document.getElementById('route-info').style.display = 'none';
    document.getElementById('reset-button').style.display = 'none';
    document.getElementById('show-route-button').style.display = 'none';
    
    // Remove custom route from map
    if(window.customRouteLayer) {
        window.customRouteLayer.remove();
        window.customRouteLayer = null;
    }
    
    // Remove custom markers
    if(window.startMarker) {
        window.startMarker.remove();
        window.startMarker = null;
    }
    
    if(window.endMarker) {
        window.endMarker.remove();
        window.endMarker = null;
    }
    
    // Reset highlighted stops
    routeData.forEach(function(stop) {
        var item = document.getElementById('stop-item-' + stop.id);
        if (item) {
            item.style.backgroundColor = '';
            item.style.padding = '';
            item.style.borderRadius = '';
        }
    });
}

// Function to display a custom route
function displayCustomRoute() {
    var startId = parseInt(document.getElementById('start-select').value);
    var endId = parseInt(document.getElementById('end-select').value);
    
    if(isNaN(startId) || isNaN(endId) || startId === endId) {
        return;
    }
    
    // Clear existing custom route and markers if any
    if(window.customRouteLayer) {
        window.customRouteLayer.remove();
    }
    
    if(window.startMarker) {
        window.startMarker.remove();
    }
    
    if(window.endMarker) {
        window.endMarker.remove();
    }
    
    // Create a new feature group for the custom route
    window.customRouteLayer = L.featureGroup();
    
    // Get the selected locations
    var startStop = routeData.find(stop => stop.id === startId);
    var endStop = routeData.find(stop => stop.id === endId);
    
    if(!startStop || !endStop) {
        return;
    }
    
    // Show the reset button and hide the show route button
    document.getElementById('reset-button').style.display = 'block';
    document.getElementById('show-route-button').style.display = 'none';
    
    // Add custom markers for the selected stops with larger, more visible designs
    window.startMarker = L.circleMarker(startStop.coords, {
        radius: 14,
        fillColor: '#1E88E5', // Bright blue
        color: '#000',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
    }).addTo(map);
    
    window.endMarker = L.circleMarker(endStop.coords, {
        radius: 14,
        fillColor: '#43A047', // Bright green
        color: '#000',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
    }).addTo(map);
    
    // Add pulsing effect to markers to make them more noticeable
    addPulsingEffect(window.startMarker._path);
    addPulsingEffect(window.endMarker._path);
    
    // Try to get the geometry for this route
    var routeKey = startId + ',' + endId;
    var geometry = routeGeometries[routeKey];
    
    if(geometry) {
        // Add the actual road path with a more visible color
        L.polyLine(
            geometry,
            {
                color: '#FF3D00', // Bright orange-red
                weight: 6,
                opacity: 0.9
            }
        ).addTo(window.customRouteLayer);
    } else {
        // Fallback to straight line with a more visible style
        L.polyLine(
            [startStop.coords, endStop.coords],
            {
                color: '#FF3D00', // Bright orange-red
                weight: 6,
                opacity: 0.9,
                dashArray: '10, 10'
            }
        ).addTo(window.customRouteLayer);
    }
    
    // Add to map
    window.customRouteLayer.addTo(map);
    
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
    
    var infoHtml = '<strong>From:</strong> ' + startStop.label + '<br>' +
                '<strong>To:</strong> ' + endStop.label + '<br>';
    
    if(directDistance !== null && directDuration !== null) {
        infoHtml += '<strong>Distance:</strong> ' + directDistance.toFixed(1) + ' km<br>' +
                '<strong>Estimated Time:</strong> ' + directDuration.toFixed(0) + ' minutes';
    } else {
        infoHtml += '<em>Direct route information not available.</em>';
    }
    
    routeInfo.innerHTML = infoHtml;
    
    // Highlight the selected stops in the list
    highlightStops(startId, endId);
    
    // Pan/zoom the map to fit the selected route
    if(window.customRouteLayer) {
        map.fitBounds(window.customRouteLayer.getBounds(), {
            padding: [50, 50]
        });
    }
}

// Function to add pulsing effect to markers
function addPulsingEffect(element) {
    if (!element) return;
    
    // Create and add the animation
    var animation = document.createElementNS("http://www.w3.org/2000/svg", "animate");
    animation.setAttribute("attributeName", "r");
    animation.setAttribute("from", "10");
    animation.setAttribute("to", "15");
    animation.setAttribute("dur", "1.5s");
    animation.setAttribute("repeatCount", "indefinite");
    
    element.appendChild(animation);
}

// Initialize sidebar when document is ready
document.addEventListener('DOMContentLoaded', function() {
    // Add the sidebar to the map
    document.body.appendChild(createSidebar());
    
    // Populate the dropdowns
    populateDropdowns();
    
    // Add event listeners
    document.getElementById('start-select').addEventListener('change', checkSelections);
    document.getElementById('end-select').addEventListener('change', checkSelections);
    document.getElementById('show-route-button').addEventListener('click', displayCustomRoute);
    document.getElementById('reset-button').addEventListener('click', resetRouteSelection);
}); 