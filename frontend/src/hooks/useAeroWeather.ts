import { useEffect, useRef, useState } from "react";
import {
  fetchLatestRainViewerRadarUrl,
  fetchLiveAviationWeather,
  getOfflineAviationWeather,
  type AviationWeather,
} from "../api/weather";

interface UseAeroWeatherProps {
  latitude?: number;
  longitude?: number;
  altitudeFt?: number;
}

export function useAeroWeather({
  latitude = 19.0760,
  longitude = 72.8777,
  altitudeFt = 35000,
}: UseAeroWeatherProps = {}) {
  const [weather, setWeather] = useState<AviationWeather>(() =>
    getOfflineAviationWeather(latitude, longitude, altitudeFt)
  );
  const [radarTileUrl, setRadarTileUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const lastFetchedCoordsRef = useRef({ lat: 0, lon: 0, alt: 0 });

  useEffect(() => {
    let isCancelled = false;

    // Trigger update if coordinates moved by > 0.01 deg (~1 km) or altitude changed > 500 ft
    const latDiff = Math.abs(lastFetchedCoordsRef.current.lat - latitude);
    const lonDiff = Math.abs(lastFetchedCoordsRef.current.lon - longitude);
    const altDiff = Math.abs(lastFetchedCoordsRef.current.alt - altitudeFt);

    if (
      latDiff < 0.01 &&
      lonDiff < 0.01 &&
      altDiff < 500 &&
      lastFetchedCoordsRef.current.lat !== 0
    ) {
      return;
    }

    lastFetchedCoordsRef.current = { lat: latitude, lon: longitude, alt: altitudeFt };

    async function loadWeather() {
      setLoading(true);
      try {
        const [liveData, radarUrl] = await Promise.all([
          fetchLiveAviationWeather(latitude, longitude, altitudeFt),
          fetchLatestRainViewerRadarUrl(),
        ]);

        if (!isCancelled) {
          setWeather(liveData);
          if (radarUrl) setRadarTileUrl(radarUrl);
        }
      } catch {
        if (!isCancelled) {
          setWeather(getOfflineAviationWeather(latitude, longitude, altitudeFt));
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    void loadWeather();

    // Auto-refresh weather every 3 minutes
    const interval = setInterval(loadWeather, 180_000);

    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [latitude, longitude, altitudeFt]);

  return {
    weather,
    radarTileUrl,
    loading,
    isLive: weather.isLive,
    refresh: () => {
      lastFetchedCoordsRef.current = { lat: 0, lon: 0, alt: 0 };
    },
  };
}
