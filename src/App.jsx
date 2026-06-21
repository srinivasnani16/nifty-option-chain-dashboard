import { useState, useEffect } from "react";
import OptionTable from "./components/OptionTable";
import Summary from "./components/Summary";

const API_BASE = "";

function App() {
  const [chain, setChain] = useState([]);
  const [summary, setSummary] = useState(null);
  const [lastUpdated, setLastUpdated] = useState("");
  const [error, setError] = useState("");

  const fetchData = async () => {
    try {
      const [chainRes, summaryRes] = await Promise.all([
        fetch(`/api/chain`),
        fetch(`/api/summary`),
      ]);
      const chainData = await chainRes.json();
      const summaryData = await summaryRes.json();
      setChain(chainData);
      setSummary(summaryData);
      setLastUpdated(new Date().toLocaleTimeString());
      setError("");
    } catch (err) {
      setError("Failed to fetch data. Check if EC2 is running.");
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ padding: "20px" }}>
      <h1 style={{ color: "#58a6ff", marginBottom: "10px" }}>
        📈 Nifty Option Chain Dashboard
      </h1>

      {error && (
        <div style={{ color: "#f85149", marginBottom: "10px" }}>{error}</div>
      )}

      <Summary summary={summary} lastUpdated={lastUpdated} />
      <OptionTable chain={chain} atm={summary?.atm_strike} />
    </div>
  );
}

export default App;