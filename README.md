# Route Optimization Model

This system optimizes delivery routes using OSRM (Open Source Routing Machine) and MapQuest geocoding API, with an interactive visualization.

## Features

- Geocodes addresses to coordinates using MapQuest API
- Gets actual road routes and distances using OSRM API
- Optimizes delivery routes using either:
  - Exact solution (brute force for up to 8 stops)
  - Nearest neighbor heuristic (for more than 8 stops)
- Creates an interactive HTML map with:
  - Actual road paths between stops
  - Distance and time estimates for each segment
  - Progress tracking for completed deliveries
  - Interactive sidebar for route management
- Implements caching of route geometries to reduce API calls

## Installation

1. Clone this repository
   ```
   git clone https://github.com/Maleleee/route-optimization-model.git
   cd route-optimization-model
   ```
2. Install required packages:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with your MapQuest API key:
   ```
   MAPQUEST_API_KEY=your_api_key_here
   ```
   You can get a free API key from [MapQuest Developer](https://developer.mapquest.com/)

## Input Data

Prepare your addresses in a CSV file named `addresses.csv` with the following format:
```
Warehouse,500 Shaw Blvd, Mandaluyong, Philippines
Stop1,SM Megamall, EDSA Corner Doña Julia Vargas Ave, Ortigas Center, Mandaluyong, Philippines
Stop2,Robinsons Galleria, EDSA corner Ortigas Avenue, Quezon City, Philippines
...
```

The first location in the CSV file is considered the warehouse/starting point.

## Running the Optimizer

```
python route-optimizer.py
```

## Output

The program will generate:
1. Detailed route information in the console
2. An interactive HTML map saved as `route_map.html`
3. A cache file for route geometries to speed up subsequent runs

### Interactive Map Features

The interactive HTML map includes:
- Actual road paths between all stops
- Interactive sidebar with:
  - Progress tracking
  - Stop completion marking
  - Distance and time estimates
  - Total route statistics
- Responsive design that works on desktop and mobile
- Detailed popups showing segment information

## Technical Details

- Uses OSRM API for precise road routing with fallback to MapQuest if OSRM fails
- Caches route geometries to reduce API calls and improve performance
- Provides actual road paths rather than straight lines
- For smaller problems (≤8 stops), uses brute-force approach to find the optimal solution
- For larger problems (>8 stops), uses nearest neighbor heuristic
- Sets Philippines as the default country for geocoding

## License

This project is open source and available under the MIT License.

## Author

[Maleleee](https://github.com/Maleleee)

