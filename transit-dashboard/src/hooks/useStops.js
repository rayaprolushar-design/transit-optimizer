import { useState, useEffect } from 'react';
import { getStops } from '../api/client';

let cachedStops = null;

export const useStops = () => {
  const [stops, setStops] = useState(cachedStops || []);
  const [loading, setLoading] = useState(!cachedStops);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (cachedStops) {
      setStops(cachedStops);
      setLoading(false);
      return;
    }

    const loadStops = async () => {
      try {
        setLoading(true);
        // Request a higher limit to ensure we fetch all stops in the network
        const data = await getStops('', 200);
        cachedStops = data;
        setStops(data);
        setError(null);
      } catch (err) {
        setError(err.response?.data?.detail || err.message || 'Failed to fetch stops');
      } finally {
        setLoading(false);
      }
    };

    loadStops();
  }, []);

  return { stops, loading, error };
};
