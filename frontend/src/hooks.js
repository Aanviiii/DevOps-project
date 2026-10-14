import { useCallback, useEffect, useRef, useState } from "react";

// Load data from an async function, re-running whenever `deps` change. Stale responses
// (from an earlier search, say) are ignored so the screen never shows old results.
export function useLoad(load, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const run = useRef(0);

  const reload = useCallback(() => {
    const id = ++run.current;
    setState((s) => ({ ...s, loading: true }));
    load()
      .then((data) => id === run.current && setState({ data, error: null, loading: false }))
      .catch((error) => id === run.current && setState({ data: null, error, loading: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(reload, [reload]);
  return { ...state, reload };
}

// Delay a fast-changing value (a search box) so we query once the user pauses.
export function useDebounced(value, ms = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}
