import React from "react";

export function TaskBoard({ spots }) {
  const visible = spots?.slice(0, 6) || [];

  if (!visible.length) {
    return <div className="empty-board">No sensor spots loaded yet. Try refreshing dashboard.</div>;
  }

  return (
    <section className="route-lane">
      {visible.map((spot) => (
        <article className="route-stop" key={spot.spot_id}>
          <p className="lesson-type">Spot</p>
          <h4>{spot.spot_id}</h4>
          <div className="lesson-meta">
            <span>{spot.parking_type}</span>
            <span>{spot.status}</span>
          </div>
        </article>
      ))}
    </section>
  );
}
