import React, { useEffect, useMemo, useState } from "react";

import { KpiCard } from "../components/KpiCard";
import { TaskBoard } from "../components/TaskBoard";

const envGatewayUrl = import.meta.env.VITE_API_GATEWAY_URL?.trim();
const gatewayUrl =
  envGatewayUrl ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:32047`
    : "http://localhost:32047");

const emptyDashboard = {
  parking: {
    parking_id: "PARK-CENTER-01",
    name: "Center Multilevel",
    parking_type: "multilevel",
    address: "12 Tverskaya St",
    total_spots: 0,
    free_spots: 0,
    base_price_per_hour: 0,
  },
  spots: { items: [] },
  analytics_kpi: {
    booking_time_seconds_avg: 0,
    booking_target_seconds: 3,
    status_update_seconds_avg: 0,
    status_update_target_seconds: 5,
    supported_spots_target: 100000,
    supports_target_booking: true,
    supports_target_status: true,
  },
  revenue: { revenue: 0 },
  hourly_load: { items: [] },
  notifications: { items: [] },
};

async function loadDashboard(parkingId) {
  const response = await fetch(`${gatewayUrl}/dashboard/${parkingId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard: ${response.status}`);
  }
  return response.json();
}

async function runFindAndBook(parkingId) {
  const payload = {
    user_id: "USR-DEMO",
    location: { lat: 55.758, lon: 37.615 },
    duration_minutes: 90,
    plate_number: "T900TT77",
    radius_km: 5,
  };
  const response = await fetch(`${gatewayUrl}/workflow/find-and-book`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Workflow failed: ${response.status}`);
  }
  const result = await response.json();
  return { parkingId, result };
}

export function DashboardPage() {
  const [parkingId, setParkingId] = useState("PARK-CENTER-01");
  const [theme, setTheme] = useState("light");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [dashboard, setDashboard] = useState(emptyDashboard);
  const [workflowResult, setWorkflowResult] = useState(null);

  useEffect(() => {
    let active = true;

    loadDashboard(parkingId)
      .then((payload) => {
        if (!active) {
          return;
        }
        setDashboard({ ...emptyDashboard, ...payload });
        setStatus("succeeded");
        setError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        setStatus("failed");
        setError(err.message);
      });

    return () => {
      active = false;
    };
  }, [parkingId]);

  const spots = dashboard.spots?.items || [];
  const notifications = dashboard.notifications?.items || [];
  const hourly = dashboard.hourly_load?.items || [];
  const occupied = Math.max((dashboard.parking?.total_spots || 0) - (dashboard.parking?.free_spots || 0), 0);

  const statusLabel = useMemo(() => {
    if (status === "loading") {
      return "loading";
    }
    if (status === "failed") {
      return "fallback";
    }
    return "live";
  }, [status]);

  const refresh = async () => {
    try {
      setStatus("loading");
      const payload = await loadDashboard(parkingId);
      setDashboard({ ...emptyDashboard, ...payload });
      setStatus("succeeded");
      setError(null);
    } catch (err) {
      setStatus("failed");
      setError(err.message);
    }
  };

  const launchWorkflow = async () => {
    try {
      const { result } = await runFindAndBook(parkingId);
      setWorkflowResult(result);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className={`app theme-${theme}`}>
      <div className="background-orb orb-a" />
      <div className="background-orb orb-b" />

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">ParkEase Smart Parking</p>
          <h1>Find, reserve, pay, and navigate to parking spots in one real-time platform.</h1>
          <p className="sub">
            ParkEase combines map discovery, sensor occupancy, plate recognition, booking, payment, and owner analytics.
          </p>
          <div className="hero-badges">
            <span>Street and private parking</span>
            <span>Dynamic pricing</span>
            <span>ANPR gate automation</span>
            <span>MQTT sensor stream</span>
          </div>
        </div>

        <div className="hero-panel">
          <label>
            Parking ID
            <input value={parkingId} onChange={(event) => setParkingId(event.target.value)} placeholder="PARK-CENTER-01" />
          </label>
          <div className="hero-actions">
            <button onClick={refresh}>Refresh dashboard</button>
            <button className="ghost" onClick={() => setTheme((current) => (current === "light" ? "dark" : "light"))}>
              Theme
            </button>
          </div>
          <button onClick={launchWorkflow}>Run find-and-book demo</button>
          <p className="status-line">Status: {statusLabel}</p>
        </div>
      </header>

      <section className="kpi-grid">
        <KpiCard
          title="Booking Time"
          value={`${Number(dashboard.analytics_kpi?.booking_time_seconds_avg || 0).toFixed(2)} sec`}
          target={`Target < ${dashboard.analytics_kpi?.booking_target_seconds || 3} sec`}
          ok={Number(dashboard.analytics_kpi?.booking_time_seconds_avg || 99) <= Number(dashboard.analytics_kpi?.booking_target_seconds || 3)}
        />
        <KpiCard
          title="Spot Status"
          value={`${Number(dashboard.analytics_kpi?.status_update_seconds_avg || 0).toFixed(2)} sec`}
          target={`Target < ${dashboard.analytics_kpi?.status_update_target_seconds || 5} sec`}
          ok={Number(dashboard.analytics_kpi?.status_update_seconds_avg || 99) <= Number(dashboard.analytics_kpi?.status_update_target_seconds || 5)}
        />
        <KpiCard
          title="Occupied Spots"
          value={`${occupied}`}
          target={`${dashboard.parking?.total_spots || 0} total`}
          ok={occupied >= 0}
        />
        <KpiCard
          title="Scaling Target"
          value={`${dashboard.analytics_kpi?.supported_spots_target || 0}`}
          target="Required: 100000"
          ok={Number(dashboard.analytics_kpi?.supported_spots_target || 0) >= 100000}
        />
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="content-grid">
        <article className="panel panel-featured">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Parking Overview</p>
              <h2>{dashboard.parking?.name}</h2>
            </div>
            <span className="pill">{dashboard.parking?.parking_type}</span>
          </div>
          <p className="panel-copy">
            {dashboard.parking?.address}. Free spots: {dashboard.parking?.free_spots}/{dashboard.parking?.total_spots}. Base price:
            {" "}{dashboard.parking?.base_price_per_hour} RUB/h.
          </p>
          <TaskBoard spots={spots} />
        </article>

        <article className="panel">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Revenue</p>
              <h2>Parking income</h2>
            </div>
            <span className="pill accent">{Math.round(dashboard.revenue?.revenue || 0).toLocaleString()} RUB</span>
          </div>
          <div className="stack-list">
            {hourly.slice(-6).reverse().map((item) => (
              <div className="stack-item" key={item.hour}>
                <div>
                  <p className="stack-title">{item.hour}:00</p>
                  <p className="stack-sub">Occupancy ratio</p>
                </div>
                <span>{Math.round(item.occupancy_ratio * 100)}%</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel panel-analytics">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Workflow Events</p>
              <h2>Notifications and last booking</h2>
            </div>
            <span className="pill">{notifications.length} messages</span>
          </div>
          {workflowResult ? (
            <div className="metrics-row">
              <div>
                <strong>{workflowResult.booking?.booking_id}</strong>
                <span>booking id</span>
              </div>
              <div>
                <strong>{workflowResult.selected_spot?.spot_id}</strong>
                <span>selected spot</span>
              </div>
              <div>
                <strong>{workflowResult.payment?.amount}</strong>
                <span>payment amount</span>
              </div>
              <div>
                <strong>{workflowResult.latency_seconds || 0}s</strong>
                <span>end-to-end latency</span>
              </div>
            </div>
          ) : (
            <div className="empty-board">Run demo workflow to see booking result snapshot.</div>
          )}
          <div className="timeline-list">
            {notifications.slice(-5).reverse().map((item, index) => (
              <div className="stack-item" key={`${item.subject}-${index}`}>
                <div>
                  <p className="stack-title">{item.subject}</p>
                  <p className="stack-sub">{item.body}</p>
                </div>
                <span>{item.channel}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
