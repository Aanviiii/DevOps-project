import { useEffect, useState } from "react";
import { getBackendVersion } from "../api";

// Set at image build time from the Git commit (see frontend/Dockerfile).
const FRONTEND_VERSION = import.meta.env.VITE_APP_VERSION ?? "dev";

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="logo" aria-hidden="true">
      <rect x="5" y="7" width="5" height="18" rx="1.2" />
      <rect x="11.5" y="4.5" width="5" height="20.5" rx="1.2" className="logo-accent" />
      <rect x="18.5" y="8" width="5" height="17" rx="1.2" transform="rotate(-12 21 16)" />
      <rect x="4" y="26" width="24" height="2" rx="1" />
    </svg>
  );
}

export default function Layout({ routes, current, children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [backendVersion, setBackendVersion] = useState(null);
  const page = routes.find((r) => r.path === current) ?? routes[0];

  useEffect(() => setMenuOpen(false), [current]);
  useEffect(() => {
    // The backend version arrives on response headers; pick it up once a call has landed.
    const timer = setInterval(() => setBackendVersion(getBackendVersion()), 1500);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className={`shell ${menuOpen ? "menu-open" : ""}`}>
      <aside className="sidebar" aria-label="Main navigation">
        <a className="brand" href="#/catalogue">
          <Logo />
          <span>
            Shelfwise
            <small>Central library desk</small>
          </span>
        </a>
        <nav>
          {routes.map((route) => (
            <a
              key={route.path}
              href={`#/${route.path}`}
              className={`nav-link ${route.path === page.path ? "is-active" : ""}`}
              aria-current={route.path === page.path ? "page" : undefined}
            >
              <span className="nav-icon" aria-hidden="true">
                {route.icon}
              </span>
              {route.label}
            </a>
          ))}
        </nav>
        <footer className="sidebar-footer">
          <span>Frontend {FRONTEND_VERSION}</span>
          <span>Backend {backendVersion ?? "…"}</span>
        </footer>
      </aside>
      <div className="scrim" onClick={() => setMenuOpen(false)} />

      <div className="main">
        <header className="topbar">
          <button
            className="icon-button menu-button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label="Open navigation"
          >
            ☰
          </button>
          <div>
            <h1>{page.label}</h1>
            <p className="subtitle">{page.subtitle}</p>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
