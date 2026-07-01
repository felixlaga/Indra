interface ErrorPanelProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorPanel({ message, onRetry }: ErrorPanelProps) {
  return (
    <div className="error-panel" role="alert">
      <div>
        <strong>Unable to load Indra data</strong>
        <p>{message}</p>
      </div>
      {onRetry ? (
        <button className="button button-secondary" type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
