import { useState } from "react";
import { api } from "../api";
import { Async, Badge } from "../components/ui";
import { plural, rupees, shortDate } from "../format";
import { useLoad } from "../hooks";

function Kpi({ label, value, note, tone }) {
  return (
    <div className={`kpi ${tone ? `kpi-${tone}` : ""}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {note && <span className="kpi-note">{note}</span>}
    </div>
  );
}

// Round the axis maximum up to a clean number so ticks read 0 / 2 / 4 / 6 …
function niceMax(value) {
  if (value <= 4) return 4;
  const step = value <= 10 ? 2 : value <= 25 ? 5 : 10;
  return Math.ceil(value / step) * step;
}

// Single-series column chart of checkouts per day. One hue, no legend (the heading
// names the series), hover/focus tooltip on each column, and a table for screen readers.
function CheckoutChart({ days }) {
  const [active, setActive] = useState(null);
  const width = 720;
  const height = 220;
  const pad = { top: 16, right: 8, bottom: 28, left: 32 };
  const max = niceMax(Math.max(...days.map((d) => d.count)));
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const band = plotW / days.length;
  const barW = Math.min(24, band * 0.6);
  const ticks = [0, max / 2, max];
  const y = (v) => pad.top + plotH - (v / max) * plotH;
  const busiest = days.reduce((a, b) => (b.count > a.count ? b : a), days[0]);

  // Rounded 4px data-end, square at the baseline.
  const column = (x, top, w, h) => {
    const r = Math.min(4, h, w / 2);
    const bottom = top + h;
    return `M${x},${bottom} V${top + r} Q${x},${top} ${x + r},${top} H${x + w - r} Q${x + w},${top} ${x + w},${top + r} V${bottom} Z`;
  };

  return (
    <figure className="chart">
      <div className="chart-inner">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Checkouts per day for the last 14 days">
        {ticks.map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} />
            <text className="chart-tick" x={pad.left - 8} y={y(t) + 4} textAnchor="end">
              {t}
            </text>
          </g>
        ))}
        {days.map((d, i) => {
          const x = pad.left + i * band + (band - barW) / 2;
          const h = (d.count / max) * plotH;
          const isActive = active === i;
          return (
            <g
              key={d.day}
              tabIndex={0}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              aria-label={`${shortDate(d.day)}: ${plural(d.count, "checkout")}`}
            >
              {/* Hit target spans the whole band, larger than the mark. */}
              <rect x={pad.left + i * band} y={pad.top} width={band} height={plotH} fill="transparent" />
              {h > 0 && <path className={`chart-bar ${isActive ? "is-active" : ""}`} d={column(x, y(d.count), barW, h)} />}
              {(i % 2 === days.length % 2 || i === days.length - 1) && (
                <text className="chart-tick" x={x + barW / 2} y={height - 8} textAnchor="middle">
                  {shortDate(d.day)}
                </text>
              )}
              {d === busiest && d.count > 0 && !isActive && (
                <text className="chart-label" x={x + barW / 2} y={y(d.count) - 6} textAnchor="middle">
                  {d.count}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {active !== null && (
        <div
          className="chart-tooltip"
          style={{ left: `${((pad.left + active * band + band / 2) / width) * 100}%` }}
          role="tooltip"
        >
          <strong>{plural(days[active].count, "checkout")}</strong>
          <span>{shortDate(days[active].day)}</span>
        </div>
      )}
      </div>
      <table className="sr-only">
        <caption>Checkouts per day</caption>
        <tbody>
          {days.map((d) => (
            <tr key={d.day}>
              <th scope="row">{d.day}</th>
              <td>{d.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

function GenreBars({ genres }) {
  const max = Math.max(1, ...genres.map((g) => g.loans));
  if (genres.length === 0) return <p className="muted">No loans yet.</p>;
  return (
    <ul className="hbars">
      {genres.map((g) => (
        <li key={g.genre} title={`${g.genre}: ${plural(g.loans, "loan")}`}>
          <span className="hbar-label">{g.genre}</span>
          <span className="hbar-track">
            <span className="hbar-fill" style={{ width: `${(g.loans / max) * 100}%` }} />
          </span>
          <span className="hbar-value">{g.loans}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Insights() {
  const stats = useLoad(() => api.stats(), []);
  const overdue = useLoad(() => api.loans.list({ state: "overdue" }), []);

  return (
    <Async result={stats}>
      {(s) => {
        const total = s.checkouts_by_day.reduce((sum, d) => sum + d.count, 0);
        return (
          <>
            <div className="kpi-grid">
              <Kpi label="Titles" value={s.titles} note={`${s.copies} copies`} />
              <Kpi label="Active members" value={s.members_active} />
              <Kpi label="On loan" value={s.on_loan} note={`${Math.round((s.on_loan / Math.max(1, s.copies)) * 100)}% of copies`} />
              <Kpi label="Overdue" value={s.overdue} tone={s.overdue > 0 ? "alert" : undefined} note={s.overdue > 0 ? "needs follow-up" : "all on time"} />
              <Kpi label="Unpaid fines" value={rupees(s.outstanding_fines)} tone={s.outstanding_fines > 0 ? "warn" : undefined} />
              <Kpi label="Holds" value={s.holds_waiting + s.holds_ready} note={`${s.holds_ready} ready to collect`} />
            </div>

            <div className="insight-grid">
              <section className="panel panel-wide">
                <header className="panel-header">
                  <h2>Checkouts per day</h2>
                  <span className="muted">{plural(total, "checkout")} in the last 14 days</span>
                </header>
                <CheckoutChart days={s.checkouts_by_day} />
              </section>

              <section className="panel">
                <header className="panel-header">
                  <h2>Most borrowed genres</h2>
                  <span className="muted">all-time loans</span>
                </header>
                <GenreBars genres={s.popular_genres} />
              </section>

              <section className="panel">
                <header className="panel-header">
                  <h2>Needs attention</h2>
                  <span className="muted">overdue loans</span>
                </header>
                {overdue.data?.length === 0 && <p className="muted">Nothing overdue. 🎉</p>}
                <ul className="plain-list">
                  {overdue.data?.slice(0, 6).map((loan) => (
                    <li key={loan.id}>
                      <span>
                        <strong>{loan.book_title}</strong>
                        <small className="muted"> · {loan.member_name}</small>
                      </span>
                      <Badge tone="red">{plural(loan.days_overdue, "day")}</Badge>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          </>
        );
      }}
    </Async>
  );
}
