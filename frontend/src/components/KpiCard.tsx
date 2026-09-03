

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
}

export function KpiCard({ title, value, subtitle }: KpiCardProps) {
  return (
    <div className="bg-surface-raised border border-surface-border rounded-lg px-5 py-4">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">{title}</p>
      <p className="text-2xl font-semibold text-white">{value}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1.5">{subtitle}</p>}
    </div>
  );
}
