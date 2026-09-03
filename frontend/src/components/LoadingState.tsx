interface LoadingStateProps {
  message?: string;
  minHeight?: string;
}

export function LoadingState({ message = "Loading...", minHeight = "h-64" }: LoadingStateProps) {
  return (
    <div className={`flex justify-center items-center ${minHeight} gap-3`}>
      <div className="h-4 w-4 border-2 border-surface-border border-t-accent rounded-full animate-spin" />
      <span className="text-sm text-text-muted">{message}</span>
    </div>
  );
}
