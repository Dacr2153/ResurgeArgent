import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { bandHex } from '../lib/band';

export type MapMode = 'pick' | 'route' | 'dashboard';

export interface MapPoint {
  lat: number;
  lng: number;
  score: number;
  title: string;
}

interface Props {
  mode: MapMode;
  height: number;
  center?: [number, number];
  zoom?: number;
  points?: MapPoint[];
  route?: [number, number][];
  /** Agrupa marcadores por densidad cuando el zoom esta lejos. */
  cluster?: boolean;
  onClusterOpen?: () => void;
}

const MAGENTA = '#d6006c';
const CYAN = '#0088b0';
const INK = '#201e1d';

function pin(color: string, glyph: string) {
  return L.divIcon({
    className: '',
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    html:
      `<div style="width:26px;height:26px;border-radius:50%;background:${color};` +
      `color:#fff;border:1.5px solid ${INK};display:flex;align-items:center;justify-content:center;` +
      `font-family:'Source Serif 4',serif;font-size:14px;font-weight:600;line-height:1;` +
      `box-shadow:0 1px 2px rgba(45,43,43,.3)">${glyph}</div>`,
  });
}

function clusterIcon(n: number, worstColor: string, worstGlyph: string) {
  return L.divIcon({
    className: '',
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    html:
      `<div style="width:40px;height:40px;border-radius:50%;background:#f3f2f2;` +
      `border:1.5px solid ${worstColor};color:${INK};display:flex;flex-direction:column;` +
      `align-items:center;justify-content:center;font-family:'Source Serif 4',serif;line-height:1;` +
      `box-shadow:0 1px 2px rgba(45,43,43,.3)">` +
      `<span style="font-size:15px;font-weight:600">${n}</span>` +
      `<span style="font-size:8px;letter-spacing:.06em;color:${worstColor}">${worstGlyph}</span></div>`,
  });
}

export function MapView({
  mode, height, center = [-12.052, -77.038], zoom = 13,
  points = [], route = [], cluster = true, onClusterOpen,
}: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  // El mapa se crea una sola vez; los datos se redibujan en el efecto siguiente.
  useEffect(() => {
    if (!holder.current || mapRef.current) return;

    const map = L.map(holder.current, {
      center,
      zoom,
      zoomControl: mode !== 'pick',
      scrollWheelZoom: mode !== 'pick',
      attributionControl: true,
    });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    // Registro de prensa: las teselas van desaturadas para que la tinta de los
    // marcadores lea primero.
    const tilePane = map.getPane('tilePane');
    if (tilePane) tilePane.style.filter = 'grayscale(1) contrast(.92) brightness(1.06)';

    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    setTimeout(() => map.invalidateSize(), 60);

    return () => { map.remove(); mapRef.current = null; layerRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    const draw = () => {
      layer.clearLayers();

      if (mode === 'pick') {
        L.marker(map.getCenter(), { icon: pin(MAGENTA, '+') }).addTo(layer);
        L.circle(map.getCenter(), { radius: 160, color: MAGENTA, weight: 1, fillOpacity: 0.06 }).addTo(layer);
        return;
      }

      if (mode === 'route' && route.length > 1) {
        L.polyline(route, { color: CYAN, weight: 4, opacity: 0.9 }).addTo(layer);
        L.circleMarker(route[0], { radius: 5, color: INK, fillColor: '#f3f2f2', fillOpacity: 1, weight: 2 }).addTo(layer);
        const dest = bandHex(92);
        L.marker(route[route.length - 1], { icon: pin(dest.color, dest.glyph) }).addTo(layer);
        map.fitBounds(L.latLngBounds(route).pad(0.25));
        return;
      }

      if (!points.length) return;

      const shouldCluster = cluster && map.getZoom() < 14;
      if (!shouldCluster) {
        points.forEach((p) => {
          const b = bandHex(p.score);
          L.marker([p.lat, p.lng], { icon: pin(b.color, b.glyph) })
            .bindTooltip(`${b.label} · ${p.title}`, { direction: 'top' })
            .addTo(layer);
        });
        return;
      }

      // Agrupacion ingenua por rejilla de pixeles (sustituye a supercluster).
      const cells = new Map<string, MapPoint[]>();
      points.forEach((p) => {
        const pt = map.latLngToContainerPoint([p.lat, p.lng]);
        const key = `${Math.floor(pt.x / 68)}:${Math.floor(pt.y / 68)}`;
        const group = cells.get(key);
        if (group) group.push(p); else cells.set(key, [p]);
      });

      cells.forEach((group) => {
        if (group.length === 1) {
          const b = bandHex(group[0].score);
          L.marker([group[0].lat, group[0].lng], { icon: pin(b.color, b.glyph) })
            .bindTooltip(`${b.label} · ${group[0].title}`, { direction: 'top' })
            .addTo(layer);
          return;
        }
        const lat = group.reduce((s, p) => s + p.lat, 0) / group.length;
        const lng = group.reduce((s, p) => s + p.lng, 0) / group.length;
        const worst = bandHex(Math.max(...group.map((p) => p.score)));
        L.marker([lat, lng], { icon: clusterIcon(group.length, worst.color, worst.glyph) })
          .on('click', () => {
            map.setView([lat, lng], Math.max(15, map.getZoom() + 2));
            onClusterOpen?.();
          })
          .bindTooltip(`${group.length} incidentes · toca para abrir`, { direction: 'top' })
          .addTo(layer);
      });
    };

    draw();
    map.on('zoomend', draw);
    return () => { map.off('zoomend', draw); };
  }, [mode, points, route, cluster, onClusterOpen]);

  return <div ref={holder} className="map" style={{ height }} role="img" aria-label="Mapa de incidentes" />;
}
