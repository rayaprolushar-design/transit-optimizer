import React, { useState } from 'react';
import { useStops } from '../hooks/useStops';
import { predictDelay, getModelInfo } from '../api/client';
import StopSearch from '../components/StopSearch';
import ErrorBanner from '../components/ErrorBanner';
import LoadingSpinner from '../components/LoadingSpinner';
import { Brain, Clock, ShieldAlert, Cpu, Thermometer, Calendar, Settings } from 'lucide-react';

function DelayPredictor() {
  const { stops, loading: stopsLoading, error: stopsError } = useStops();
  const [modelMeta, setModelMeta] = useState(null);
  const [modelLoading, setModelLoading] = useState(false);

  // Form Fields
  const [selectedStop, setSelectedStop] = useState(null);
  const [hour, setHour] = useState(new Date().getHours());
  const [isWeekend, setIsWeekend] = useState(0);
  const [priorStopDelay, setPriorStopDelay] = useState(0);
  const [tempDeviation, setTempDeviation] = useState(0.0);
  const [stopSequenceNorm, setStopSequenceNorm] = useState(0.5);
  const [routeType, setRouteType] = useState(3); // 3=Bus, 1=Metro
  const [nStopsOnTrip, setNStopsOnTrip] = useState(6);

  // States
  const [prediction, setPrediction] = useState(null);
  const [predictLoading, setPredictLoading] = useState(false);
  const [error, setError] = useState(null);

  React.useEffect(() => {
    const loadModelMeta = async () => {
      setModelLoading(true);
      try {
        const data = await getModelInfo();
        setModelMeta(data);
      } catch (err) {
        console.error('Failed to load model meta:', err);
      } finally {
        setModelLoading(false);
      }
    };
    loadModelMeta();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedStop) {
      setError('Please select a stop to predict delay');
      return;
    }

    setPredictLoading(true);
    setError(null);
    setPrediction(null);

    const payload = {
      stop_id: selectedStop.stop_id,
      hour: parseInt(hour),
      is_weekend: parseInt(isWeekend),
      prior_stop_delay: parseFloat(priorStopDelay) || 0.0,
      temp_deviation: parseFloat(tempDeviation) || 0.0,
      stop_sequence_norm: parseFloat(stopSequenceNorm) || 0.0,
      route_type: parseInt(routeType),
      n_stops_on_trip: parseInt(nStopsOnTrip) || 1,
    };

    try {
      const data = await predictDelay(payload);
      setPrediction(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Delay prediction failed');
    } finally {
      setPredictLoading(false);
    }
  };

  const getConfidenceBadge = (confidence) => {
    switch (confidence) {
      case 'high':
        return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.15)]';
      case 'medium':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.15)]';
      case 'low':
      default:
        return 'bg-rose-500/10 text-rose-400 border border-rose-500/20 shadow-[0_0_10px_rgba(244,63,94,0.15)]';
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8 h-full max-w-[1600px] mx-auto fade-in-up">
      {/* Input Parameters Form */}
      <div className="lg:col-span-7 flex flex-col gap-6">
        <div className="bg-dark-850 border border-dark-800 rounded-2xl p-6 glass-panel">
          <h3 className="font-display font-bold text-lg text-slate-100 mb-5 flex items-center gap-2">
            <Brain className="w-5 h-5 text-brand-neonPurple" />
            ML Feature Parameters
          </h3>

          {(stopsError || error) && (
            <div className="mb-4">
              <ErrorBanner message={stopsError || error} onDismiss={() => setError(null)} />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Stop Selector */}
            <StopSearch
              id="predict-stop"
              stops={stops}
              selectedStop={selectedStop}
              onChange={setSelectedStop}
              placeholder="Search stop to analyze..."
              label="Stop to Predict"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Hour of Day */}
              <div>
                <label htmlFor="hour" className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Hour of Day (0-23)
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                    <Clock className="w-4 h-4" />
                  </div>
                  <input
                    id="hour"
                    type="number"
                    min="0"
                    max="23"
                    value={hour}
                    onChange={(e) => setHour(e.target.value)}
                    className="w-full bg-dark-900 border border-dark-800 rounded-xl py-3 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-neonPurple/50 focus:ring-1 focus:ring-brand-neonPurple/50 transition-all"
                  />
                </div>
              </div>

              {/* Day Type Toggle */}
              <div>
                <label className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Day of Week
                </label>
                <div className="flex bg-dark-900 p-1 rounded-xl border border-dark-800 h-[46px] items-center">
                  <button
                    type="button"
                    onClick={() => setIsWeekend(0)}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                      isWeekend === 0
                        ? 'bg-brand-neonPurple text-white shadow-sm shadow-neon-purple'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Weekday
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsWeekend(1)}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                      isWeekend === 1
                        ? 'bg-brand-neonPurple text-white shadow-sm shadow-neon-purple'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Weekend
                  </button>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Prior Delay */}
              <div>
                <label htmlFor="prior-delay" className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Prior Stop Delay (minutes)
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                    <ShieldAlert className="w-4 h-4" />
                  </div>
                  <input
                    id="prior-delay"
                    type="number"
                    step="0.1"
                    min="0"
                    value={priorStopDelay}
                    onChange={(e) => setPriorStopDelay(e.target.value)}
                    className="w-full bg-dark-900 border border-dark-800 rounded-xl py-3 pl-10 pr-4 text-sm text-slate-100 focus:outline-none focus:border-brand-neonPurple/50 focus:ring-1 focus:ring-brand-neonPurple/50 transition-all"
                  />
                </div>
              </div>

              {/* Temperature Deviation */}
              <div>
                <label htmlFor="temp-dev" className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Temp Deviation from Avg (&deg;C)
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                    <Thermometer className="w-4 h-4" />
                  </div>
                  <input
                    id="temp-dev"
                    type="number"
                    step="0.1"
                    value={tempDeviation}
                    onChange={(e) => setTempDeviation(e.target.value)}
                    className="w-full bg-dark-900 border border-dark-800 rounded-xl py-3 pl-10 pr-4 text-sm text-slate-100 focus:outline-none focus:border-brand-neonPurple/50 focus:ring-1 focus:ring-brand-neonPurple/50 transition-all"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Route Type */}
              <div>
                <label className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Transit Mode
                </label>
                <div className="flex bg-dark-900 p-1 rounded-xl border border-dark-800 h-[46px] items-center">
                  <button
                    type="button"
                    onClick={() => setRouteType(3)}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                      routeType === 3
                        ? 'bg-brand-neonPurple text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Bus
                  </button>
                  <button
                    type="button"
                    onClick={() => setRouteType(1)}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                      routeType === 1
                        ? 'bg-brand-neonPurple text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Metro
                  </button>
                </div>
              </div>

              {/* Stop Sequence Norm */}
              <div>
                <label htmlFor="stop-seq" className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Stop Position (0.0 - 1.0)
                </label>
                <input
                  id="stop-seq"
                  type="number"
                  step="0.05"
                  min="0.0"
                  max="1.0"
                  value={stopSequenceNorm}
                  onChange={(e) => setStopSequenceNorm(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-800 rounded-xl py-3 px-4 text-sm text-slate-100 focus:outline-none focus:border-brand-neonPurple/50 focus:ring-1 focus:ring-brand-neonPurple/50 transition-all h-[46px]"
                />
              </div>

              {/* Stops on Trip */}
              <div>
                <label htmlFor="stops-on-trip" className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider block">
                  Total Stops on Trip
                </label>
                <input
                  id="stops-on-trip"
                  type="number"
                  min="1"
                  value={nStopsOnTrip}
                  onChange={(e) => setNStopsOnTrip(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-800 rounded-xl py-3 px-4 text-sm text-slate-100 focus:outline-none focus:border-brand-neonPurple/50 focus:ring-1 focus:ring-brand-neonPurple/50 transition-all h-[46px]"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={stopsLoading || predictLoading || !selectedStop}
              className="w-full bg-gradient-to-r from-brand-neonPurple to-brand-neonPink text-white font-bold py-3.5 rounded-xl transition-all duration-300 shadow-neon-purple hover:brightness-110 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none text-sm flex items-center justify-center gap-2"
            >
              <Brain className="w-4.5 h-4.5" />
              Generate Delay Prediction
            </button>
          </form>
        </div>
      </div>

      {/* Results Display Panel */}
      <div className="lg:col-span-5 flex flex-col gap-6">
        {/* Loading details */}
        {predictLoading && <LoadingSpinner message="Calculating ML delay prediction..." />}

        {/* Prediction Results */}
        {prediction && !predictLoading && (
          <div className="bg-dark-850 border border-dark-800 rounded-2xl p-6 glass-panel flex flex-col items-center justify-center space-y-6 fade-in-up">
            <div className="w-16 h-16 rounded-2xl bg-brand-neonPurple/10 border border-brand-neonPurple/20 flex items-center justify-center text-brand-neonPurple shadow-neon-purple">
              <Clock className="w-9 h-9" />
            </div>

            <div className="text-center space-y-1">
              <h4 className="font-display font-bold text-slate-100 text-lg">
                {prediction.stop_name}
              </h4>
              <p className="text-xs text-slate-500 font-semibold uppercase tracking-widest">
                ID: {prediction.stop_id}
              </p>
            </div>

            <div className="text-center space-y-1 relative">
              {/* Glow backdrop */}
              <div className="absolute inset-0 filter blur-xl opacity-30 bg-brand-neonPurple animate-pulse" />
              <span className="text-6xl font-display font-extrabold text-white tracking-tight relative">
                {prediction.predicted_delay.toFixed(1)}
              </span>
              <span className="text-sm font-semibold text-slate-400 block relative">
                minutes expected delay
              </span>
            </div>

            {/* Confidence & Cache status */}
            <div className="flex gap-3 justify-center w-full">
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${getConfidenceBadge(prediction.confidence)}`}>
                {prediction.confidence} Confidence
              </span>

              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${
                prediction.cached 
                  ? 'bg-brand-neonBlue/10 text-brand-neonBlue border-brand-neonBlue/20' 
                  : 'bg-slate-800 text-slate-400 border-dark-700'
              }`}>
                {prediction.cached ? 'CACHE HIT' : 'API EVAL'}
              </span>
            </div>

            {/* Model Evaluation Info */}
            <div className="w-full border-t border-dark-800/60 pt-4 space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-400">Model Mean Absolute Error</span>
                <span className="text-slate-200 font-bold">{prediction.model_mae.toFixed(3)} min</span>
              </div>
              {modelMeta && (
                <>
                  <div className="flex justify-between text-xs font-medium">
                    <span className="text-slate-400">Model Architecture</span>
                    <span className="text-slate-200 font-bold truncate max-w-[200px]">{modelMeta.model_name}</span>
                  </div>
                  <div className="flex justify-between text-xs font-medium">
                    <span className="text-slate-400">Test R&sup2; Score</span>
                    <span className="text-slate-200 font-bold">{(modelMeta.test_r2 * 100).toFixed(1)}%</span>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Info card if no prediction has been generated */}
        {!prediction && !predictLoading && (
          <div className="bg-dark-850 border border-dark-800 rounded-2xl p-6 glass-panel flex flex-col items-center justify-center text-center space-y-4 h-full min-h-[300px]">
            <Settings className="w-10 h-10 text-brand-neonPurple animate-spin" style={{ animationDuration: '6s' }} />
            <div>
              <h4 className="font-display font-bold text-slate-200">Prediction Telemetry</h4>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed max-w-xs mx-auto">
                Modify features in the parameters panel and trigger the prediction request. The ML pipeline will resolve arrival delays based on historical telemetry.
              </p>
            </div>
          </div>
        )}

        {/* Model Metadata summary card */}
        {modelMeta && (
          <div className="bg-dark-850 border border-dark-800 rounded-2xl p-5 glass-panel space-y-3.5">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
              <Cpu className="w-4 h-4 text-brand-neonPink animate-pulse" />
              ML Model Registry
            </h4>
            <div className="grid grid-cols-2 gap-3 text-[11px] font-medium text-slate-400">
              <div className="bg-dark-900/40 p-3 rounded-xl border border-dark-800">
                <span className="block text-slate-500 mb-0.5">TRAIN ROWS</span>
                <span className="text-slate-200 font-bold">{modelMeta.n_train.toLocaleString()}</span>
              </div>
              <div className="bg-dark-900/40 p-3 rounded-xl border border-dark-800">
                <span className="block text-slate-500 mb-0.5">CV MAE MEAN</span>
                <span className="text-slate-200 font-bold">{modelMeta.cv_mae_mean.toFixed(3)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default DelayPredictor;
