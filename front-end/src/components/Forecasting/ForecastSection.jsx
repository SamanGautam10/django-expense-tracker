import "./styles.css";

import React, { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import { API } from "../../api-service";

const COLORS = {
  actual: "rgb(255,140,0)",
  baseline: "rgb(0,123,255)",
  forest: "rgb(220,53,69)",
};

const shortDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
  });

const euro = (n) => `€${Number(n).toFixed(2)}`;

const ForecastSection = ({ accessToken }) => {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | ready | error

  useEffect(() => {
    let cancelled = false;
    API.fetchForecast(accessToken)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setStatus("ready");
        }
      })
      .catch((err) => {
        console.error("Forecast error:", err);
        if (!cancelled) setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  if (status === "loading")
    return <div className='forecast-card forecast-msg'>Building your forecast…</div>;
  if (status === "error")
    return <div className='forecast-card forecast-msg'>Forecast unavailable right now.</div>;

  if (data.status !== "ok") {
    return (
      <div className='forecast-card forecast-msg'>
        Not enough spending history for a forecast yet. It needs at least{" "}
        {data.needed_active_days} days with expenses in the last {data.window_days} days
        (you have {data.active_days}).
      </div>
    );
  }

  const { month, metrics, daily, recent_actual } = data;
  const up = month.direction === "higher";

  const pad = recent_actual.length;
  const blanks = (n) => Array(n).fill(null);
  const line = (label, color, values, dash) => ({
    label,
    data: values,
    borderColor: color,
    backgroundColor: color,
    borderDash: dash,
    fill: false,
    tension: 0,
    pointRadius: 3,
  });

  const chartData = {
    labels: [...recent_actual, ...daily].map((d) => shortDate(d.date)),
    datasets: [
      line("Actual", COLORS.actual, [
        ...recent_actual.map((d) => d.amount),
        ...blanks(daily.length),
      ]),
      line(
        "Same-weekday average",
        COLORS.baseline,
        [...blanks(pad), ...daily.map((d) => d.baseline)],
        [6, 6]
      ),
      line(
        "Random Forest",
        COLORS.forest,
        [...blanks(pad), ...daily.map((d) => d.random_forest)],
        [2, 4]
      ),
    ],
  };

  // react-chartjs-2 v2 / Chart.js v2 option names (title, scales.yAxes) - not the v3+ "plugins.title"
  const options = {
    responsive: true,
    title: { display: true, text: "Daily spending: last 14 days and 7-day forecast" },
    legend: { display: true },
    scales: {
      yAxes: [
        {
          ticks: { beginAtZero: true },
          scaleLabel: { display: true, labelString: "(€) Amounts" },
        },
      ],
    },
  };

  const best = metrics?.winner;
  const label = (k) => (k === "random_forest" ? "Random Forest" : "Same-weekday average");

  return (
    <div className='forecast-card'>
      <h5>Spending forecast</h5>

      <div className={`forecast-headline ${up ? "forecast-higher" : "forecast-lower"}`}>
        <span className='forecast-arrow'>{up ? "▲" : "▼"}</span>
        <div>
          <strong>
            This month is projected to be {up ? "higher" : "lower"} than last month
          </strong>
          <div className='forecast-sub'>
            Projected {euro(month.projected)} vs {euro(month.previous)} last month · spent so
            far {euro(month.to_date)}
            {month.scheduled > 0 && ` · plus ${euro(month.scheduled)} already dated later this month`}
            {month.budget
              ? ` · budget ${euro(month.budget)} (${
                  month.vs_budget > 0
                    ? `${euro(month.vs_budget)} over`
                    : `${euro(-month.vs_budget)} under`
                })`
              : ""}
          </div>
        </div>
      </div>

      <Line data={chartData} options={options} />

      {metrics ? (
        <p className='forecast-metrics'>
          Back-test on the last {metrics.test_days} days (lower is better) — Same-weekday
          average: MAE {euro(metrics.same_weekday.mae)}, RMSE {euro(metrics.same_weekday.rmse)} ·
          Random Forest: MAE {euro(metrics.random_forest.mae)}, RMSE{" "}
          {euro(metrics.random_forest.rmse)}. Month projection uses: {label(best)}.
        </p>
      ) : (
        <p className='forecast-metrics'>
          Not enough history to back-test the models yet; using the same-weekday average.
        </p>
      )}
    </div>
  );
};

export default ForecastSection;
