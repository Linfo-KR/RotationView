import heapq
import math

class RouteFinder:
    def __init__(self, resolution=5):
        """
        resolution: Grid size in degrees (Lower = more precise but slower)
        5 degrees is very coarse, good for quick PoC.
        """
        self.resolution = resolution
        self.width = int(360 / resolution)
        self.height = int(180 / resolution)
        self.grid = [[0 for _ in range(self.width)] for _ in range(self.height)]
        
        # Simple Land Mask (0=Sea, 1=Land)
        # This is a VERY rough approximation of continents for testing logic
        self._init_land_mask()

    def _init_land_mask(self):
        # Define rough bounding boxes for continents [lat_min, lat_max, lng_min, lng_max]
        continents = [
            # Africa/Eurasia block
            [0, 70, -20, 140], 
            # North America
            [15, 70, -170, -50],
            # South America
            [-60, 15, -90, -30],
            # Australia
            [-40, -10, 110, 160]
        ]

        for lat_idx in range(self.height):
            for lng_idx in range(self.width):
                lat = 90 - (lat_idx * self.resolution)
                lng = -180 + (lng_idx * self.resolution)
                
                is_land = False
                for box in continents:
                    if box[0] <= lat <= box[1] and box[2] <= lng <= box[3]:
                        is_land = True
                        break
                
                if is_land:
                    self.grid[lat_idx][lng_idx] = 1

    def _coords_to_grid(self, lat, lng):
        lat_idx = int((90 - lat) / self.resolution)
        lng_idx = int((lng + 180) / self.resolution)
        
        # Clamp
        lat_idx = max(0, min(lat_idx, self.height - 1))
        lng_idx = max(0, min(lng_idx, self.width - 1))
        
        return lat_idx, lng_idx

    def _grid_to_coords(self, lat_idx, lng_idx):
        lat = 90 - (lat_idx * self.resolution)
        lng = -180 + (lng_idx * self.resolution)
        return lat, lng

    def _heuristic(self, a, b):
        # Manhattan distance on grid (simple heuristic)
        # Handle wrapping for longitude (Pacific crossing)
        dx = abs(a[1] - b[1])
        if dx > self.width / 2: # Wrap around
            dx = self.width - dx
        dy = abs(a[0] - b[0])
        return dx + dy

    def find_path(self, start_lat, start_lng, end_lat, end_lng):
        start = self._coords_to_grid(start_lat, start_lng)
        end = self._coords_to_grid(end_lat, end_lng)
        
        # Priority Queue for A*: (cost, (lat_idx, lng_idx))
        frontier = []
        heapq.heappush(frontier, (0, start))
        
        came_from = {}
        cost_so_far = {}
        
        came_from[start] = None
        cost_so_far[start] = 0
        
        found = False
        
        print(f"[Info] Pathfinding from {start} to {end}...")

        while frontier:
            _, current = heapq.heappop(frontier)
            
            if current == end:
                found = True
                break
            
            # Neighbors (Up, Down, Left, Right)
            # Include diagonals for smoother paths? Let's stick to 4-way for now.
            r, c = current
            neighbors = [
                (r+1, c), (r-1, c), 
                (r, (c+1) % self.width), # Wrap East
                (r, (c-1 + self.width) % self.width) # Wrap West
            ]
            
            for next_node in neighbors:
                nr, nc = next_node
                
                # Check bounds (Lat shouldn't wrap)
                if 0 <= nr < self.height:
                    # Check if land
                    if self.grid[nr][nc] == 1:
                        continue
                        
                    new_cost = cost_so_far[current] + 1 # Uniform cost
                    if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                        cost_so_far[next_node] = new_cost
                        priority = new_cost + self._heuristic(next_node, end)
                        heapq.heappush(frontier, (priority, next_node))
        
        if not found:
            print("[Warn] Path not found!")
            return []
            
        # Reconstruct path
        path = []
        curr = end
        while curr != start:
            path.append(self._grid_to_coords(*curr))
            curr = came_from[curr]
        path.append(self._grid_to_coords(*start))
        path.reverse()
        
        return path

def main():
    finder = RouteFinder(resolution=2) # 2 degree grid
    
    # Test: Busan (35, 129) to Long Beach (33, -118)
    # Should cross Pacific (wrap around), avoiding North America land mass
    print("Test Case 1: Busan -> Long Beach")
    path = finder.find_path(35, 129, 33, -118)
    
    print(f"Path points: {len(path)}")
    if len(path) > 0:
        print(f"Start: {path[0]}")
        print(f"Mid: {path[len(path)//2]}")
        print(f"End: {path[-1]}")
        
    # Test: Rotterdam (51, 4) to New York (40, -74)
    # Should cross Atlantic
    print("\nTest Case 2: Rotterdam -> New York")
    path2 = finder.find_path(51, 4, 40, -74)
    print(f"Path points: {len(path2)}")

if __name__ == "__main__":
    main()
