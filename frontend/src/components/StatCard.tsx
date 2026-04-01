interface Props {
  label: string;
  value: string | number;
  sub?: string;
}

export default function StatCard({ label, value, sub }: Props) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <p className="text-xs text-muted uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-text mt-1">{value}</p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  );
}
