import { API_URL } from "../constants/config";

export const api = {
  async getStops() {
    const res = await fetch(`${API_URL}/stops?limit=100`);
    if (!res.ok) throw new Error("Failed to fetch stops");
    return res.json();
  },
  async getRoute(from, to, algorithm) {
    const res = await fetch(`${API_URL}/route?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&algorithm=${algorithm}`);
    if (!res.ok) throw new Error("Failed to fetch route");
    return res.json();
  },
  async predictDelay(payload) {
    const res = await fetch(`${API_URL}/predict-delay-ci`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to predict delay");
    return res.json();
  },
  async getBoard(stopId) {
    const res = await fetch(`${API_URL}/board/${stopId}`);
    if (!res.ok) throw new Error("Failed to fetch departure board");
    return res.json();
  }
};

export default { api };
