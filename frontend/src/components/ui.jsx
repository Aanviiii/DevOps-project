import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------- toasts

const ToastContext = createContext(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(1);

  const notify = useCallback((message, tone = "success") => {
    const id = nextId.current++;
    setToasts((all) => [...all, { id, message, tone }]);
    setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), 4500);
  }, []);

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// Run an API action, then toast its outcome. Returns true when it succeeded.
export function useAction() {
  const notify = useToast();
  return useCallback(
    async (action, successMessage) => {
      try {
        const result = await action();
        if (successMessage) notify(successMessage(result));
        return true;
      } catch (error) {
        notify(error.message, "error");
        return false;
      }
    },
    [notify],
  );
}

// ---------------------------------------------------------------- modal

export function Modal({ title, onClose, children, wide = false }) {
  const dialog = useRef(null);

  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    dialog.current?.querySelector("input, select, button")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className={`modal ${wide ? "modal-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={dialog}
      >
        <header className="modal-header">
          <h2>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- small pieces

export const Badge = ({ tone = "neutral", children }) => (
  <span className={`badge badge-${tone}`}>{children}</span>
);

export const Field = ({ label, hint, children }) => (
  <label className="field">
    <span className="field-label">{label}</span>
    {children}
    {hint && <span className="field-hint">{hint}</span>}
  </label>
);

export function Loading({ label = "Loading" }) {
  return (
    <div className="loading" aria-busy="true">
      <span className="spinner" /> {label}…
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="state-card state-error" role="alert">
      <strong>Something went wrong.</strong>
      <p>{error.message}</p>
      {onRetry && (
        <button className="button button-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="state-card">
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}

// Render loading, error and empty states consistently around a list.
export function Async({ result, empty, children }) {
  if (result.loading && !result.data) return <Loading />;
  if (result.error) return <ErrorState error={result.error} onRetry={result.reload} />;
  if (empty && result.data?.length === 0) return empty;
  return children(result.data);
}
