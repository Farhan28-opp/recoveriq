import type { ReactNode } from "react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  highlight?: boolean;
}

export function StatCard({ title, value, subtitle, icon, highlight }: StatCardProps) {
  return (
    <div className={`p-5 rounded-xl border transition-shadow duration-200 hover:shadow-card-hover ${
      highlight
        ? "bg-accent-light border-accent-border"
        : "bg-surface-raised border-surface-border shadow-card"
    }`}>
      <div className="flex justify-between items-start mb-3">
        <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">{title}</p>
        {icon && (
          <div className={`p-1.5 rounded-lg ${highlight ? "bg-accent/10 text-accent" : "bg-surface-overlay text-text-subtle"}`}>
            {icon}
          </div>
        )}
      </div>
      <p className={`text-2xl font-bold tracking-tight ${highlight ? "text-accent" : "text-text-primary"}`}>
        {value}
      </p>
      {subtitle && (
        <p className="text-[11px] text-text-muted mt-1.5">{subtitle}</p>
      )}
    </div>
  );
}
