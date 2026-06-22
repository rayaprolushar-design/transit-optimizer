import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getHealth = async () => {
  const response = await api.get('/');
  return response.data;
};

export const getStops = async (filter = '', limit = 100) => {
  const response = await api.get('/stops', {
    params: { filter, limit },
  });
  return response.data;
};

export const getRoute = async (fromStop, toStop, algorithm = 'astar', transfers = true) => {
  const response = await api.get('/route', {
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
  // payload format matches DelayRequest:
  // { stop_id, hour, is_weekend, prior_stop_delay, temp_deviation, stop_sequence_norm, route_type, n_stops_on_trip }
  const response = await api.post('/predict-delay', payload);
  return response.data;
};

export const getModelInfo = async () => {
  const response = await api.get('/model-info');
  return response.data;
};

export const getStats = async () => {
  const response = await api.get('/stats');
  return response.data;
};

export default {
  getHealth,
  getStops,
  getRoute,
  predictDelay,
  getModelInfo,
  getStats,
};
