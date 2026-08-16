/**
 * api/client.js
 * Axios client pointing at your Railway FastAPI backend.
 * Same endpoints as the React web dashboard — identical API.
 */
import axios from "axios"
import { API_URL } from "../constants/config"

const client = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
})

client.interceptors.response.use(
  res => res,
  err => {
    const msg = err.response?.data?.detail ?? err.message ?? "Unknown error"
    return Promise.reject(new Error(msg))
  }
)

export const api = {
  health:       ()          => client.get("/").then(r => r.data),
  getStops:     (filter="") => client.get("/stops", { params: { filter, limit: 100 } }).then(r => r.data),
  getRoute:     (from, to, algorithm="astar") =>
                  client.get("/route", { params: { from, to, algorithm } }).then(r => r.data),
  predictDelay: (payload)   => client.post("/predict-delay", payload).then(r => r.data),
  predictCI:    (payload)   => client.post("/predict-delay-ci", payload).then(r => r.data),
  liveDelays:   ()          => client.get("/live-delays").then(r => r.data),
  stopDelay:    (stopId)    => client.get(`/live-delays/${stopId}`).then(r => r.data),
  boardData:    (stopId)    => client.get(`/board/${stopId}?n=5`).then(r => r.data),
  modelHealth:  ()          => client.get("/model-health").then(r => r.data),
  stats:        ()          => client.get("/stats").then(r => r.data),
}

export default client
