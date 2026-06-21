function OptionTable({ chain, atm }) {
  if (!chain || chain.length === 0)
    return <p style={{ color: "#8b949e" }}>Loading option chain...</p>;

  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          background: "#161b22",
          borderRadius: "8px",
          overflow: "hidden",
        }}
      >
        <thead>
          <tr style={{ background: "#21262d", color: "#8b949e", fontSize: "12px" }}>
            <th style={th}>CE OI (lots)</th>
            <th style={th}>CE COI</th>
            <th style={th}>CE Vol</th>
            <th style={th}>CE LTP</th>
            <th style={{ ...th, color: "#58a6ff", fontSize: "14px" }}>STRIKE</th>
            <th style={th}>PE LTP</th>
            <th style={th}>PE Vol</th>
            <th style={th}>PE COI</th>
            <th style={th}>PE OI (lots)</th>
          </tr>
        </thead>
        <tbody>
          {chain.map((row, i) => {
            const isATM = row.strike === atm;
            return (
              <tr
                key={i}
                style={{
                  background: isATM ? "#1f2d3d" : i % 2 === 0 ? "#161b22" : "#0d1117",
                  borderLeft: isATM ? "3px solid #58a6ff" : "3px solid transparent",
                }}
              >
                <td style={{ ...td, color: "#f85149" }}>{row.ce_oi?.toLocaleString()}</td>
                <td style={{ ...td, color: "#f85149" }}>{row.ce_coi?.toLocaleString()}</td>
                <td style={{ ...td, color: "#f85149" }}>{row.ce_volume?.toLocaleString()}</td>
                <td style={{ ...td, color: "#f85149" }}>{row.ce_ltp}</td>
                <td style={{ ...td, color: "#e3b341", fontWeight: "bold", fontSize: "15px", textAlign: "center" }}>
                  {row.strike}
                </td>
                <td style={{ ...td, color: "#3fb950" }}>{row.pe_ltp}</td>
                <td style={{ ...td, color: "#3fb950" }}>{row.pe_volume?.toLocaleString()}</td>
                <td style={{ ...td, color: "#3fb950" }}>{row.pe_coi?.toLocaleString()}</td>
                <td style={{ ...td, color: "#3fb950" }}>{row.pe_oi?.toLocaleString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const th = {
  padding: "10px 12px",
  textAlign: "right",
  fontWeight: "600",
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};

const td = {
  padding: "8px 12px",
  textAlign: "right",
  borderBottom: "1px solid #21262d",
};

export default OptionTable;