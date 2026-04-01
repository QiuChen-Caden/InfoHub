interface Props {
  label: string;
  value: string | number;
  sub?: string;
}

export default function StatCard({ label, value, sub }: Props) {
  return (
    <div className="bb-panel">
      <div className="bb-panel-header">{label}</div>
      <div className="bb-panel-body">
        <p className="text-xl font-bold text-accent">{value}</p>
        {sub && <p className="text-xs text-accent/70 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}
