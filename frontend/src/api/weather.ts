/**
 * AeroGuard Live Aviation Weather Service
 *
 * Integrates live global meteorological data from Open-Meteo & RainViewer APIs:
 * - Real-time surface & winds aloft observations
 * - WMO Weather classification & aviation sky conditions
 * - Altimeter pressure (QNH in hPa and inHg)
 * - Automatic ISA lapse rate calculation for current aircraft Flight Level
 * - Simulated ICAO METAR generation
 * - Live Doppler precipitation radar tile stream
 * - Robust deterministic offline fallback for air-gapped simulation environments
 *
 * SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
 */

export interface AviationWeather {
  timestamp: string;
  stationId: string;
  stationName: string;
  latitude: number;
  longitude: number;
  condition: string;
  icon: string;
  wmoCode: number;
  surfaceTempC: number;
  surfaceTempF: number;
  temperatureAloftC: number;
  temperatureAloftF: number;
  windSpeedKt: number;
  windDirectionDeg: number;
  windGustKt?: number;
  surfacePressureHpa: number;
  altimeterInHg: number;
  relativeHumidity: number;
  cloudCoverPercent: number;
  dewPointC: number;
  flightLevel: string;
  metarRaw: string;
  radarTileUrl?: string;
  isLive: boolean;
}

const WMO_WEATHER_TABLE: Record<number, { label: string; icon: string }> = {
  0: { label: "Clear Sky", icon: "☀" },
  1: { label: "Mainly Clear", icon: "🌤" },
  2: { label: "Partly Cloudy", icon: "⛅" },
  3: { label: "Overcast", icon: "☁" },
  45: { label: "Fog", icon: "🌫" },
  48: { label: "Depositing Rime Fog", icon: "🌫" },
  51: { label: "Light Drizzle", icon: "🌦" },
  53: { label: "Moderate Drizzle", icon: "🌧" },
  55: { label: "Dense Drizzle", icon: "🌧" },
  61: { label: "Slight Rain", icon: "🌦" },
  63: { label: "Moderate Rain", icon: "🌧" },
  65: { label: "Heavy Rain", icon: "🌧" },
  71: { label: "Slight Snow", icon: "🌨" },
  73: { label: "Moderate Snow", icon: "🌨" },
  75: { label: "Heavy Snow", icon: "❄" },
  80: { label: "Rain Showers", icon: "🌦" },
  82: { label: "Violent Rain Showers", icon: "⛈" },
  95: { label: "Thunderstorm", icon: "⛈" },
  96: { label: "Thunderstorm w/ Hail", icon: "⛈" },
  99: { label: "Severe Thunderstorm", icon: "⛈" },
};

function getWmoDetails(code: number): { label: string; icon: string } {
  return WMO_WEATHER_TABLE[code] ?? { label: "Fair", icon: "☀" };
}

/**
 * Standard ISA temperature lapse rate calculation:
 * T(altitude) = T_surface - (1.98°C per 1,000 ft) up to tropopause (36,089 ft)
 */
function calculateTemperatureAloft(surfaceTempC: number, altitudeFt: number): number {
  const lapseRatePerThousand = 1.98;
  const clampedAltitude = Math.min(altitudeFt, 36089);
  const tempAloft = surfaceTempC - (clampedAltitude / 1000) * lapseRatePerThousand;
  return Math.round(tempAloft * 10) / 10;
}

/**
 * Approximates dew point from temperature and relative humidity
 */
function calculateDewPoint(tempC: number, rh: number): number {
  return Math.round((tempC - (100 - rh) / 5) * 10) / 10;
}

export interface AerodromeStation {
  id: string;
  name: string;
  lat: number;
  lon: number;
  airway: string;
}

export const REGIONAL_AERODROMES: AerodromeStation[] = [
  { id: "VABB", name: "Mumbai Chhatrapati Shivaji Maharaj Intl", lat: 19.0896, lon: 72.8656, airway: "V124 (BOM)" },
  { id: "VAPO", name: "Pune Lohegaon Airfield / Western Corridor", lat: 18.5821, lon: 73.9197, airway: "V124 (PNQ)" },
  { id: "VOHS", name: "Hyderabad Rajiv Gandhi Intl", lat: 17.2403, lon: 78.4294, airway: "V124 (HYD)" },
  { id: "VAID", name: "Indore Devi Ahilya Bai Holkar Intl", lat: 22.7218, lon: 75.8011, airway: "W23 (IDR)" },
  { id: "VOBL", name: "Bengaluru Kempegowda Intl", lat: 13.1986, lon: 77.7066, airway: "Q21 (BLR)" },
  { id: "VOGO", name: "Goa Dabolim Airport", lat: 15.3808, lon: 73.8314, airway: "W15 (GOI)" },
  { id: "VANP", name: "Nagpur Dr. Babasaheb Ambedkar Intl", lat: 21.0922, lon: 79.0594, airway: "V45 (NAG)" },
  { id: "VIDP", name: "Delhi Indira Gandhi Intl", lat: 28.5562, lon: 77.1000, airway: "V1 (DEL)" },
];

/**
 * Dynamically resolves the nearest reporting aerodrome for the flight's exact coordinates.
 */
export function resolveNearestStation(lat: number, lon: number): { stationId: string; stationName: string } {
  let nearest = REGIONAL_AERODROMES[0];
  let minDistance = Infinity;

  for (const aero of REGIONAL_AERODROMES) {
    const dLat = aero.lat - lat;
    const dLon = (aero.lon - lon) * Math.cos((lat * Math.PI) / 180);
    const distSq = dLat * dLat + dLon * dLon;
    if (distSq < minDistance) {
      minDistance = distSq;
      nearest = aero;
    }
  }

  const distNm = Math.round(Math.sqrt(minDistance) * 60);
  if (distNm <= 25) {
    return {
      stationId: nearest.id,
      stationName: `${nearest.name} [${nearest.airway}]`,
    };
  }
  return {
    stationId: nearest.id,
    stationName: `${nearest.name} (${distNm} NM out - ${nearest.airway})`,
  };
}

export interface FlightWaypoint {
  id: string;
  name: string;
  lat: number;
  lon: number;
  time: string;
  stationId: string;
}

export const FLIGHT_WAYPOINTS: FlightWaypoint[] = [
  { id: "WP1", name: "Mumbai (VABB)", lat: 19.0760, lon: 72.8777, time: "12:00", stationId: "VABB" },
  { id: "WP2", name: "Pune (VAPO)", lat: 18.5204, lon: 73.8567, time: "12:08", stationId: "VAPO" },
  { id: "WP3", name: "Hyderabad (VOHS)", lat: 17.3850, lon: 78.4867, time: "12:18", stationId: "VOHS" },
];

export interface FlightRoutePosition {
  latitude: number;
  longitude: number;
  heading: number;
  legLabel: string;
  stationId: string;
  stationName: string;
}

/**
 * Computes exact position and heading along the airway corridor based on scenario progress.
 */
export function computeFlightRoutePosition(progressRatio: number): FlightRoutePosition {
  const r = Math.max(0, Math.min(1, progressRatio));
  const wp1 = FLIGHT_WAYPOINTS[0];
  const wp2 = FLIGHT_WAYPOINTS[1];
  const wp3 = FLIGHT_WAYPOINTS[2];

  if (r <= 0.5) {
    const t = r / 0.5;
    const lat = wp1.lat + (wp2.lat - wp1.lat) * t;
    const lon = wp1.lon + (wp2.lon - wp1.lon) * t;
    const station = resolveNearestStation(lat, lon);
    return {
      latitude: Math.round(lat * 10000) / 10000,
      longitude: Math.round(lon * 10000) / 10000,
      heading: 120,
      legLabel: "LEG 1: BOM -> PUN (Airway V124)",
      stationId: station.stationId,
      stationName: station.stationName,
    };
  } else {
    const t = (r - 0.5) / 0.5;
    const lat = wp2.lat + (wp3.lat - wp2.lat) * t;
    const lon = wp2.lon + (wp3.lon - wp2.lon) * t;
    const station = resolveNearestStation(lat, lon);
    return {
      latitude: Math.round(lat * 10000) / 10000,
      longitude: Math.round(lon * 10000) / 10000,
      heading: 102,
      legLabel: "LEG 2: PUN -> HYD (Airway V124)",
      stationId: station.stationId,
      stationName: station.stationName,
    };
  }
}

/**
 * Generates an authentic simulated ICAO METAR string from parameters
 */
function generateSimulatedMetar(params: {
  station: string;
  windDir: number;
  windSpeed: number;
  tempC: number;
  dewPointC: number;
  pressureHpa: number;
  cloudCover: number;
}): string {
  const now = new Date();
  const day = String(now.getUTCDate()).padStart(2, "0");
  const hour = String(now.getUTCHours()).padStart(2, "0");
  const minute = "00";
  const zuluTime = `${day}${hour}${minute}Z`;

  const windStr = `${String(Math.round(params.windDir)).padStart(3, "0")}${String(Math.round(params.windSpeed)).padStart(2, "0")}KT`;
  const cloudCode = params.cloudCover < 10 ? "SKC" : params.cloudCover < 30 ? "FEW025" : params.cloudCover < 60 ? "SCT040" : "BKN070";
  const tempDew = `${params.tempC < 0 ? "M" : ""}${String(Math.abs(Math.round(params.tempC))).padStart(2, "0")}/${params.dewPointC < 0 ? "M" : ""}${String(Math.abs(Math.round(params.dewPointC))).padStart(2, "0")}`;
  const qnhStr = `Q${Math.round(params.pressureHpa)}`;

  return `METAR ${params.station} ${zuluTime} ${windStr} 9999 ${cloudCode} ${tempDew} ${qnhStr} NOSIG`;
}

// In-memory cache to prevent excessive requests
interface CacheEntry {
  data: AviationWeather;
  cachedAt: number;
}
const weatherCache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 180_000; // 3 minutes

/**
 * Deterministic offline ISA weather fallback
 */
export function getOfflineAviationWeather(lat = 19.0760, lon = 72.8777, altitudeFt = 35000): AviationWeather {
  const { stationId, stationName } = resolveNearestStation(lat, lon);
  const surfaceTempC = 28.0;
  const aloftC = calculateTemperatureAloft(surfaceTempC, altitudeFt);
  const dewPoint = calculateDewPoint(surfaceTempC, 75);

  return {
    timestamp: new Date().toISOString(),
    stationId,
    stationName,
    latitude: lat,
    longitude: lon,
    condition: "Clear Sky",
    icon: "☀",
    wmoCode: 0,
    surfaceTempC,
    surfaceTempF: Math.round((surfaceTempC * 9) / 5 + 32),
    temperatureAloftC: aloftC,
    temperatureAloftF: Math.round((aloftC * 9) / 5 + 32),
    windSpeedKt: 14,
    windDirectionDeg: 280,
    surfacePressureHpa: 1012,
    altimeterInHg: 29.88,
    relativeHumidity: 75,
    cloudCoverPercent: 15,
    dewPointC: dewPoint,
    flightLevel: `FL${Math.round(altitudeFt / 100)}`,
    metarRaw: generateSimulatedMetar({
      station: stationId,
      windDir: 280,
      windSpeed: 14,
      tempC: surfaceTempC,
      dewPointC: dewPoint,
      pressureHpa: 1012,
      cloudCover: 15,
    }),
    isLive: false,
  };
}

/**
 * Fetches live weather from Open-Meteo with automatic fallback and caching
 */
export async function fetchLiveAviationWeather(
  lat = 19.0760,
  lon = 72.8777,
  altitudeFt = 35000
): Promise<AviationWeather> {
  const cacheKey = `${lat.toFixed(2)},${lon.toFixed(2)},${Math.round(altitudeFt / 1000)}`;
  const cached = weatherCache.get(cacheKey);
  if (cached && Date.now() - cached.cachedAt < CACHE_TTL_MS) {
    return cached.data;
  }

  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure&wind_speed_unit=kn`;

    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timeout = setTimeout(() => controller?.abort(), 3500);

    const response = await fetch(url, {
      signal: controller?.signal,
      headers: { Accept: "application/json" },
    });
    clearTimeout(timeout);

    if (!response.ok) {
      throw new Error(`Open-Meteo returned status ${response.status}`);
    }

    const payload = await response.json();
    const current = payload.current;

    const surfaceTempC = typeof current.temperature_2m === "number" ? current.temperature_2m : 27.0;
    const wmoCode = typeof current.weather_code === "number" ? current.weather_code : 0;
    const { label, icon } = getWmoDetails(wmoCode);
    const windSpeedKt = typeof current.wind_speed_10m === "number" ? Math.round(current.wind_speed_10m) : 10;
    const windDir = typeof current.wind_direction_10m === "number" ? Math.round(current.wind_direction_10m) : 270;
    const pressureHpa = typeof current.surface_pressure === "number" ? Math.round(current.surface_pressure * 10) / 10 : 1012.0;
    const rh = typeof current.relative_humidity_2m === "number" ? current.relative_humidity_2m : 70;
    const cloudCover = typeof current.cloud_cover === "number" ? current.cloud_cover : 10;

    const { stationId, stationName } = resolveNearestStation(lat, lon);
    const aloftC = calculateTemperatureAloft(surfaceTempC, altitudeFt);
    const dewPoint = calculateDewPoint(surfaceTempC, rh);
    const altimeterInHg = Math.round((pressureHpa * 0.02953) * 100) / 100;

    const weatherData: AviationWeather = {
      timestamp: current.time ?? new Date().toISOString(),
      stationId,
      stationName,
      latitude: lat,
      longitude: lon,
      condition: label,
      icon,
      wmoCode,
      surfaceTempC: Math.round(surfaceTempC * 10) / 10,
      surfaceTempF: Math.round((surfaceTempC * 9) / 5 + 32),
      temperatureAloftC: aloftC,
      temperatureAloftF: Math.round((aloftC * 9) / 5 + 32),
      windSpeedKt,
      windDirectionDeg: windDir,
      windGustKt: current.wind_gusts_10m ? Math.round(current.wind_gusts_10m) : undefined,
      surfacePressureHpa: pressureHpa,
      altimeterInHg,
      relativeHumidity: rh,
      cloudCoverPercent: cloudCover,
      dewPointC: dewPoint,
      flightLevel: `FL${Math.round(altitudeFt / 100)}`,
      metarRaw: generateSimulatedMetar({
        station: stationId,
        windDir,
        windSpeed: windSpeedKt,
        tempC: surfaceTempC,
        dewPointC: dewPoint,
        pressureHpa,
        cloudCover,
      }),
      isLive: true,
    };

    weatherCache.set(cacheKey, { data: weatherData, cachedAt: Date.now() });
    return weatherData;
  } catch {
    // Return deterministic ISA weather on network timeout / test mock environments
    const fallback = getOfflineAviationWeather(lat, lon, altitudeFt);
    return fallback;
  }
}

/**
 * Fetches the latest RainViewer weather radar timestamp for live Doppler tiles
 */
export async function fetchLatestRainViewerRadarUrl(): Promise<string | null> {
  try {
    const response = await fetch("https://api.rainviewer.com/public/weather-maps.json");
    if (!response.ok) return null;
    const json = await response.json();
    const host = json.host || "https://tilecache.rainviewer.com";
    const past = json.radar?.past;
    if (Array.isArray(past) && past.length > 0) {
      const latestPath = past[past.length - 1].path;
      return `${host}${latestPath}/256/{z}/{x}/{y}/2/1_1.png`;
    }
    return null;
  } catch {
    return null;
  }
}
