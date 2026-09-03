import { AlertTriangle } from "lucide-react";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  message = "Something went wrong",
  onRetry,
}: ErrorStateProps) {
  const isConnectionError =
    message.toLowerCase().includes("fetch") ||
    message.toLowerCase().includes("network") ||
    message.toLowerCase().includes("connect");

  return (
    <div className="max-w-md mx-auto my-8 bg-red-50 border border-red-200 rounded-xl p-6 text-center animate-fade-in">
      <AlertTriangle className="w-7 h-7 text-red-500 mx-auto mb-3" />
      <h3 className="text-sm font-semibold text-red-700 mb-1">
        {isConnectionError ? "Unable to connect to RecoverIQ" : "Error"}
      </h3>
      <p className="text-xs text-red-600 mb-1">
        {isConnectionError ? "Check that the backend is running." : message}
      </p>
      {isConnectionError && (
        <p className="text-[11px] text-red-500/70 mb-4">
          Expected at: {import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-1.5 bg-white border border-red-200 text-red-600 text-xs font-medium rounded-lg hover:bg-red-50 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
