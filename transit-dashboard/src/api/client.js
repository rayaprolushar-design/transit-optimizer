import axios from 'axios';

const baseURL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? '/api' : 'https://transit-optimizer-production-cea3.up.railway.app');

const axiosInstance = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getHealth = async () => {
  const response = await axiosInstance.get('/');
  return response.data;
};

export const getStops = async (filter = '', limit = 100) => {
  const response = await axiosInstance.get('/stops', {
    params: { filter, limit },
  });
  return response.data;
};

export const getRoute = async (fromStop, toStop, algorithm = 'astar', transfers = true) => {
  const response = await axiosInstance.get('/route', {
    params: {
      from: fromStop,
      to: toStop,
      algorithm,
      transfers,
    },
  });
  return response.data;
};

export const predictDelay = async (payload) => {
  const response = await axiosInstance.post('/predict-delay', payload);
  return response.data;
};

export const getModelInfo = async () => {
  const response = await axiosInstance.get('/model-info');
  return response.data;
};

export const getStats = async () => {
  const response = await axiosInstance.get('/stats');
  return response.data;
};

// Export the unified api object expected by the new Analytics dashboard
export const api = {
  stats: getStats,
  modelInfo: getModelInfo,
  health: getHealth,
  stops: getStops,
  route: getRoute,
  predictDelay: predictDelay,
};

export default {
  getHealth,
  getStops,
  getRoute,
  predictDelay,
  getModelInfo,
  getStats,
  api,
};
