import { useState } from 'react';
import { getRoute } from '../api/client';

export const useRoute = () => {
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const calculateRoute = async (fromStop, toStop, algorithm = 'astar', transfers = true) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRoute(fromStop, toStop, algorithm, transfers);
      setRoute(data);
      return data;
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to calculate route';
      setError(errMsg);
      setRoute(null);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const clearRoute = () => {
    setRoute(null);
    setError(null);
  };

  return { route, result: route, loading, error, calculateRoute, search: calculateRoute, clearRoute };
};
