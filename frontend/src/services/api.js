import axios from 'axios';

// Use environment variable for API URL or default to localhost
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const routeService = {
  // Get all available routes
  getAllRoutes: async (year = null) => {
    try {
      // Increase limit to fetch more routes for testing
      const url = year ? `/routes?limit=1000&year=${year}` : '/routes?limit=1000';
      const response = await api.get(url);
      return response.data;
    } catch (error) {
      console.error('Error fetching routes:', error);
      throw error;
    }
  },
  
  // Get distinct years available in database
  getRouteYears: async () => {
    try {
      const response = await api.get('/routes/years');
      return response.data;
    } catch (error) {
      console.error('Error fetching route years:', error);
      throw error;
    }
  },
  
  // Get detailed information for a specific route
  getRouteById: async (id) => {
    try {
      const response = await api.get(`/routes/${id}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching route ${id}:`, error);
      throw error;
    }
  },
  
  // Fix port mismatch (alias mapping)
  fixPortMismatch: async (routeIdx, badPortName, correctPortCode) => {
    try {
      const response = await api.post('/fix-port-mismatch', {
        route_idx: routeIdx,
        bad_port_name: badPortName,
        correct_port_code: correctPortCode
      });
      return response.data;
    } catch (error) {
      console.error('Error fixing port mismatch:', error);
      throw error;
    }
  }
};

export const portService = {
  // Get all ports
  getAllPorts: async () => {
    try {
      // Fetch all ports (increase limit to cover ~6000 records)
      const response = await api.get('/ports?limit=10000');
      return response.data;
    } catch (error) {
      console.error('Error fetching ports:', error);
      throw error;
    }
  }
};

export default api;
