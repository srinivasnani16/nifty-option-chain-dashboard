function Summary({ summary, lastUpdated }) {
  if (!summary) return <p style={{ color: "#8b949e" }}>Loading summary...</p>;

  const sentimentColor =
    summary.sentiment === "Bullish"
      ? "#3fb950"
      : summary.sentiment === "Bearish"
      ? "#f85149"
      : "#e3b341";

  return (
    <div
      style={{
        display: "flex",
        gap: "20px",
        flexWrap: "wrap",
        marginBottom: "20px",
        background: "#161b22",
        padding: "16px",
        borderRadius: "8px",
        border: "1px solid #30363d",
      }}
    >
      <Tile label="ATM Strike" value={summary.atm_strike} />
      <Tile label="Total CE OI (lots)" value={summary.total_ce_oi?.toLocaleString()} />
      <Tile label="Total PE OI (lots)" value={summary.total_pe_oi?.toLocaleString()} />
      <Tile label="PCR" value={summary.pcr} />
      <Tile
        label="Sentiment"
        value={summary.sentiment}
        color={sentimentColor}
      />
      <Tile label="Last Updated" value={lastUpdated} color="#8b949e" />
    </div>
  );
}

function Tile({ label, value, color }) {
  return (
    <div style={{ minWidth: "130px" }}>
      <div style={{ color: "#8b949e", fontSize: "12px", marginBottom: "4px" }}>
        {label}
      </div>
      <div style={{ color: color || "#e6edf3", fontSize: "18px", fontWeight: "bold" }}>
        {value ?? "—"}
      </div>
    </div>
  );
}

export default Summary;