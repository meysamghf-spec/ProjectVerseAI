export function OriginBadge({ origin }: { origin: string }) {
  const label =
    origin === "user"
      ? "User-provided"
      : origin === "calculated"
        ? "Calculated"
        : origin === "simulation"
          ? "Simulation"
          : origin === "inferred"
            ? "Inferred"
            : "Assumption";
  const tone =
    origin === "user" ? "user" : origin === "calculated" ? "calculated" : origin === "simulation" ? "simulation" : "assumption";
  return <span className={`badge ${tone}`}>{label}</span>;
}

export function Disclaimer({ children }: { children: string }) {
  return (
    <p className="rounded-xl border border-amber/30 bg-amber/10 px-3 py-2 text-sm text-amber">
      {children}
    </p>
  );
}
