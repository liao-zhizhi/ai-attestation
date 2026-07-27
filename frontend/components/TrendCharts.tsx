"use client";

export type DayPoint = { day: string; calls: number; cost: number; marks: number };
export type VendorSlice = { vendor: string; count: number; color: string };

type Props = {
  series: DayPoint[];
  vendors: VendorSlice[];
};

function maxOf(arr: number[], fallback = 1) {
  return Math.max(...arr, fallback);
}

export function TrendCharts({ series, vendors }: Props) {
  const w = 420;
  const h = 120;
  const pad = 8;
  const maxCalls = maxOf(series.map((d) => d.calls));
  const maxCost = maxOf(series.map((d) => d.cost), 0.0001);
  const maxMarks = maxOf(series.map((d) => d.marks));

  function poly(values: number[], peak: number) {
    if (!values.length) return "";
    return values
      .map((v, i) => {
        const x = pad + (i / Math.max(values.length - 1, 1)) * (w - pad * 2);
        const y = h - pad - (v / peak) * (h - pad * 2);
        return `${x},${y}`;
      })
      .join(" ");
  }

  const totalV = vendors.reduce((s, v) => s + v.count, 0) || 1;
  let angle = -Math.PI / 2;
  const arcs = vendors.map((v) => {
    const sweep = (v.count / totalV) * Math.PI * 2;
    const x1 = 60 + Math.cos(angle) * 48;
    const y1 = 60 + Math.sin(angle) * 48;
    angle += sweep;
    const x2 = 60 + Math.cos(angle) * 48;
    const y2 = 60 + Math.sin(angle) * 48;
    const large = sweep > Math.PI ? 1 : 0;
    return {
      ...v,
      d: `M 60 60 L ${x1} ${y1} A 48 48 0 ${large} 1 ${x2} ${y2} Z`,
    };
  });

  return (
    <div className="charts">
      <section>
        <h3>过去 7 天趋势</h3>
        <svg viewBox={`0 0 ${w} ${h}`} className="line">
          <polyline
            fill="none"
            stroke="#3dd68c"
            strokeWidth="2"
            points={poly(
              series.map((d) => d.calls),
              maxCalls
            )}
          />
          <polyline
            fill="none"
            stroke="#f0b429"
            strokeWidth="2"
            points={poly(
              series.map((d) => d.cost),
              maxCost
            )}
          />
          <polyline
            fill="none"
            stroke="#ff6b6b"
            strokeWidth="1.5"
            strokeDasharray="4 3"
            points={poly(
              series.map((d) => d.marks),
              maxMarks
            )}
          />
        </svg>
        <div className="legend mono">
          <span className="g">调用</span>
          <span className="y">费用</span>
          <span className="r">标记</span>
        </div>
        <div className="days mono">
          {series.map((d) => (
            <span key={d.day}>{d.day.slice(5)}</span>
          ))}
        </div>
      </section>
      <section>
        <h3>厂商分布</h3>
        {vendors.length === 0 ? (
          <p className="empty">暂无厂商数据</p>
        ) : (
          <div className="pie-wrap">
            <svg viewBox="0 0 120 120" className="pie">
              {arcs.map((a) => (
                <path key={a.vendor} d={a.d} fill={a.color} />
              ))}
              <circle cx="60" cy="60" r="22" fill="#0e141c" />
            </svg>
            <ul>
              {vendors.map((v) => (
                <li key={v.vendor}>
                  <i style={{ background: v.color }} />
                  <span className="mono">
                    {v.vendor} · {v.count}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
      <style jsx>{`
        .charts {
          display: grid;
          grid-template-columns: 1.6fr 1fr;
          gap: 12px;
          margin-bottom: 16px;
        }
        section {
          background: #111821;
          border: 1px solid #1e2a38;
          border-radius: 6px;
          padding: 12px 14px;
        }
        h3 {
          margin: 0 0 10px;
          font-size: 12px;
          color: #7f8fa3;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .line {
          width: 100%;
          height: 120px;
        }
        .legend {
          display: flex;
          gap: 12px;
          font-size: 11px;
          margin-top: 6px;
        }
        .g {
          color: #3dd68c;
        }
        .y {
          color: #f0b429;
        }
        .r {
          color: #ff6b6b;
        }
        .days {
          display: flex;
          justify-content: space-between;
          margin-top: 4px;
          font-size: 10px;
          color: #7f8fa3;
        }
        .pie-wrap {
          display: flex;
          gap: 14px;
          align-items: center;
        }
        .pie {
          width: 120px;
          height: 120px;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 6px;
        }
        li {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
        }
        i {
          width: 8px;
          height: 8px;
          border-radius: 2px;
          display: inline-block;
        }
        .empty {
          color: #7f8fa3;
          font-family: var(--mono);
          font-size: 12px;
        }
        .mono {
          font-family: var(--mono);
        }
        @media (max-width: 900px) {
          .charts {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
