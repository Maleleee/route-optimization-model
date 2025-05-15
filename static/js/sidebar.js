// Global variables
let map;
let markers = [];
let polylines = [];
let completedStops = new Set();
let currentRoute = null;

// Initialize the map
function initMap() {
    // Create map instance
    map = L.map('map').setView([0, 0], 2);
    
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Initialize sidebar
    initSidebar();
}

// Initialize sidebar functionality
function initSidebar() {
    const toggleButton = document.getElementById('toggle-sidebar');
    const sidebar = document.getElementById('sidebar');
    const showRouteButton = document.getElementById('show-route-button');
    const resetButton = document.getElementById('reset-button');
    const startSelect = document.getElementById('start-select');
    const endSelect = document.getElementById('end-select');

    // Toggle sidebar
    toggleButton.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        toggleButton.innerHTML = sidebar.classList.contains('collapsed') ? '&raquo;' : '&laquo;';
    });

    // Show route button click handler
    showRouteButton.addEventListener('click', () => {
        const startId = startSelect.value;
        const endId = endSelect.value;
        if (startId && endId) {
            showRoute(startId, endId);
        }
    });

    // Reset button click handler
    resetButton.addEventListener('click', () => {
        resetRoute();
    });
}

// Add markers to the map
function addMarkers(stops) {
    // Clear existing markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    // Add new markers
    stops.forEach(stop => {
        const marker = L.marker([stop.lat, stop.lng])
            .bindPopup(`
                <strong>${stop.name}</strong><br>
                Address: ${stop.address}<br>
                Estimated Time: ${stop.estimated_time} hours
            `)
            .addTo(map);

        marker.on('click', () => {
            toggleStopCompletion(stop.id);
        });

        markers.push(marker);
    });

    // Fit map to markers
    if (markers.length > 0) {
        const group = new L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

// Show route between two points
function showRoute(startId, endId) {
    // Clear existing route
    clearRoute();

    // Find start and end markers
    const startMarker = markers.find(m => m.stopId === startId);
    const endMarker = markers.find(m => m.stopId === endId);

    if (startMarker && endMarker) {
        // Create polyline
        const polyline = L.polyline([
            [startMarker.getLatLng().lat, startMarker.getLatLng().lng],
            [endMarker.getLatLng().lat, endMarker.getLatLng().lng]
        ], {
            color: '#3498db',
            weight: 4,
            opacity: 0.7
        }).addTo(map);

        polylines.push(polyline);

        // Update route info
        updateRouteInfo(startMarker, endMarker);

        // Show reset button
        document.getElementById('reset-button').style.display = 'block';
    }
}

// Clear current route
function clearRoute() {
    polylines.forEach(polyline => map.removeLayer(polyline));
    polylines = [];
    document.getElementById('route-info').style.display = 'none';
    document.getElementById('reset-button').style.display = 'none';
}

// Reset route selection
function resetRoute() {
    clearRoute();
    document.getElementById('start-select').value = '';
    document.getElementById('end-select').value = '';
    document.getElementById('show-route-button').style.display = 'none';
}

// Toggle stop completion
function toggleStopCompletion(stopId) {
    if (completedStops.has(stopId)) {
        completedStops.delete(stopId);
    } else {
        completedStops.add(stopId);
    }
    updateProgress();
}

// Update progress display
function updateProgress() {
    const totalStops = markers.length;
    const completedCount = completedStops.size;
    const progressPercent = (completedCount / totalStops) * 100;

    // Update progress bar
    document.getElementById('progress-fill').style.width = `${progressPercent}%`;
    
    // Update counts
    document.getElementById('progress-count').textContent = `${completedCount}/${totalStops}`;
    document.getElementById('completed-count').textContent = `${completedCount}/${totalStops}`;
}

// Update route information display
function updateRouteInfo(startMarker, endMarker) {
    const routeInfo = document.getElementById('route-info');
    const distance = calculateDistance(
        startMarker.getLatLng().lat,
        startMarker.getLatLng().lng,
        endMarker.getLatLng().lat,
        endMarker.getLatLng().lng
    );
    const time = calculateTime(distance);

    routeInfo.innerHTML = `
        <h3 style="margin: 0 0 10px 0; color: #2c3e50;">Route Information</h3>
        <div style="margin-bottom: 10px;">
            <strong>From:</strong> ${startMarker.getPopup().getContent().split('<br>')[0].replace('<strong>', '').replace('</strong>', '')}
        </div>
        <div style="margin-bottom: 10px;">
            <strong>To:</strong> ${endMarker.getPopup().getContent().split('<br>')[0].replace('<strong>', '').replace('</strong>', '')}
        </div>
        <div style="margin-bottom: 5px;">
            <strong>Distance:</strong> ${distance.toFixed(1)} km
        </div>
        <div>
            <strong>Estimated Time:</strong> ${time.toFixed(1)} hours
        </div>
    `;
    routeInfo.style.display = 'block';
}

// Calculate distance between two points using Haversine formula
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in kilometers
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * 
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// Convert degrees to radians
function toRad(degrees) {
    return degrees * (Math.PI/180);
}

// Calculate estimated time based on distance
function calculateTime(distance) {
    const averageSpeed = 50; // km/h
    return distance / averageSpeed;
}

// Initialize the map when the page loads
document.addEventListener('DOMContentLoaded', initMap); 