export function ProbabilityGauge({ probability }: { probability: number }) {
  const percent = Math.round(probability * 100);
  // Color-code: high is good (green), low is poor (red)
  const barColor =
    percent >= 70
      ? "bg-emerald-500"
      : percent >= 45
      ? "bg-blue-500"
      : "bg-red-400";

  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs font-medium text-text-muted">Recovery probability</span>
        <span className={`text-2xl font-bold tracking-tight ${
          percent >= 70 ? "text-emerald-600" : percent >= 45 ? "text-blue-600" : "text-red-500"
        }`}>
          {percent}%
        </span>
      </div>
      <div className="w-full bg-surface-overlay rounded-full h-2 overflow-hidden border border-surface-border">
        <div
          className={`h-2 rounded-full transition-all duration-700 ease-out ${barColor}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="text-[11px] text-text-subtle mt-1.5">
        {percent >= 70 ? "Strong recovery signal" : percent >= 45 ? "Moderate recovery potential" : "Low recovery likelihood"}
      </p>
    </div>
  );
}
