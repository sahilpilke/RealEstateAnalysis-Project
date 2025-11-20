import React, { useState } from "react";
import axios from "axios";
import "bootstrap/dist/css/bootstrap.min.css";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

function App() {
  const [query, setQuery] = useState("");
  const [summary, setSummary] = useState("");
  const [chartData, setChartData] = useState({});
  const [tableData, setTableData] = useState([]);
  const [recentQueries, setRecentQueries] = useState([]);
  const [loading, setLoading] = useState(false);

  // 🔥 Using your deployed Render backend
  const API_BASE_URL = "https://realestate-backend-soou.onrender.com";

  const suggested = [
    "Compare Ambegaon Budruk and Aundh demand trends",
    "Show price growth for Akurdi over the last 3 years",
    "Average price trend for Wakad",
    "Which area has highest demand?",
    "Show demand trend for Aundh",
  ];

  const applyQuery = (q) => setQuery(q);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/analyze/`, {
        query: query,
      });

      setSummary(response.data.summary);
      setChartData(response.data.chart_data);
      setTableData(response.data.table_data);

      setRecentQueries((prev) => [query, ...prev.slice(0, 4)]);
    } catch (error) {
      console.error(error);
      alert("Error connecting to backend");
    }

    setLoading(false);
  };

  const handleDownloadXLSX = async () => {
    if (tableData.length === 0) {
      alert("No data available to download.");
      return;
    }

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/download-xlsx/`,
        { table_data: tableData },
        { responseType: "blob" }
      );

      const blob = new Blob([response.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "filtered_data.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      alert("Failed to download file.");
    }
  };

  return (
    <div className="container-fluid min-vh-100 bg-dark text-light py-4">
      <div className="row g-4">

        {/* LEFT: Query + Recent */}
        <div className="col-lg-8">
          <div className="card bg-secondary border-0 shadow-sm">
            <div className="card-body py-3">
              <h3 className="fw-bold text-white mb-3">Enter Your Query</h3>

              <form onSubmit={handleAnalyze} className="d-flex gap-2">
                <input
                  type="text"
                  className="form-control bg-dark text-white border-light"
                  placeholder="e.g. Analyze Wakad prices"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />

                <button type="submit" className="btn btn-primary px-4">
                  Analyze
                </button>
              </form>

              {loading && <div className="text-info mt-2">Processing…</div>}

              <div className="mt-4">
                <h5 className="text-white fw-bold">Recent Queries</h5>

                {recentQueries.length === 0 && (
                  <p className="text-muted">No recent queries yet</p>
                )}

                <div className="d-flex flex-wrap gap-2 mt-2">
                  {recentQueries.map((q, i) => (
                    <span
                      key={i}
                      className="badge bg-primary p-2"
                      style={{ cursor: "pointer" }}
                      onClick={() => applyQuery(q)}
                    >
                      {q}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT: Suggested */}
        <div className="col-lg-4">
          <div className="card bg-secondary border-0 shadow-sm">
            <div className="card-body py-3">
              <h4 className="fw-bold text-white">Suggested Queries</h4>

              <div className="mt-3 d-flex flex-column gap-2">
                {suggested.map((s, i) => (
                  <button
                    key={i}
                    className="btn btn-outline-info text-start"
                    onClick={() => applyQuery(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* SUMMARY */}
      {summary && (
        <div className="card bg-secondary border-0 shadow-sm mt-4">
          <div className="card-body">
            <h3 className="fw-bold text-white">Summary</h3>
            <p className="mt-3 text-light">{summary}</p>
          </div>
        </div>
      )}

      {/* CHARTS */}
      {chartData && Object.keys(chartData).length > 0 && (
        <div className="card bg-secondary border-0 shadow-sm mt-4">
          <div className="card-body">
            <h3 className="fw-bold text-white mb-3">Charts</h3>

            {Object.entries(chartData).map(([area, data]) => (
              <div key={area} className="my-4">

                <h5 className="fw-bold text-info">{area}</h5>

                <h6 className="text-light mt-3">Price Trend</h6>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={data}>
                    <XAxis dataKey="year" stroke="#fff" />
                    <YAxis stroke="#fff" />
                    <CartesianGrid strokeDasharray="3 3" stroke="#888" />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="price" stroke="#00d1ff" strokeWidth={3} />
                  </LineChart>
                </ResponsiveContainer>

                <h6 className="text-light mt-4">Demand Trend</h6>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={data}>
                    <XAxis dataKey="year" stroke="#fff" />
                    <YAxis stroke="#fff" />
                    <CartesianGrid strokeDasharray="3 3" stroke="#888" />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="demand" stroke="#00ff99" strokeWidth={3} />
                  </LineChart>
                </ResponsiveContainer>

              </div>
            ))}
          </div>
        </div>
      )}

      {/* TABLE + DOWNLOAD */}
      {tableData.length > 0 && (
        <div className="card bg-secondary border-0 shadow-sm mt-4 mb-5">
          <div className="card-body">

            <div className="d-flex justify-content-between align-items-center">
              <h3 className="fw-bold text-white">Data Table</h3>
              <button onClick={handleDownloadXLSX} className="btn btn-success">
                Download Excel
              </button>
            </div>

            <div className="table-responsive mt-3" style={{ maxHeight: "500px", overflowY: "auto" }}>
              <table className="table table-dark table-striped table-hover">
                <thead>
                  <tr>
                    {Object.keys(tableData[0]).map((col, i) => (
                      <th key={i} className="text-info">{col}</th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {tableData.map((row, i) => (
                    <tr key={i}>
                      {Object.values(row).map((val, j) => (
                        <td key={j}>{val !== null ? val.toString() : "-"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>

              </table>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}

export default App;
