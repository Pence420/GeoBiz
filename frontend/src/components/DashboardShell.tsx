import type { ReactNode } from "react";

export type ViewKey = "overview" | "analytics" | "demographics" | "methodology";

const destinations: Array<{ view: ViewKey; hash: string; label: string }> = [
  { view: "overview", hash: "#overview", label: "Map Explorer" },
  { view: "analytics", hash: "#analytics", label: "Analytics" },
  { view: "demographics", hash: "#demographics", label: "Demographics" },
  { view: "methodology", hash: "#methodology-view", label: "Methodology" },
];

const pageCopy: Record<ViewKey, { eyebrow: string; title: string; description: string }> = {
  overview: { eyebrow: "LOCATION INTELLIGENCE", title: "Explore Jakarta", description: "Bukti spasial untuk memilih lokasi bisnis." },
  analytics: { eyebrow: "MARKET CONTEXT", title: "Analytics", description: "Bandingkan pola usaha dan peluang wilayah." },
  demographics: { eyebrow: "RESIDENT POPULATION", title: "Demographics", description: "Struktur penduduk wilayah, bukan profil pelanggan." },
  methodology: { eyebrow: "DATA & METHODS", title: "Methodology", description: "Telusuri sumber, definisi, dan batasan skor." },
};

function RailIcon({ view }: { view: ViewKey }) {
  const paths: Record<ViewKey, ReactNode> = {
    overview: <><path d="m3 6 6-2 6 2 6-2v14l-6 2-6-2-6 2z" /><path d="M9 4v14m6-12v14" /></>,
    analytics: <><path d="M4 19V9m5 10V5m5 14v-7m5 7V8" /><path d="M3 21h18" /></>,
    demographics: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6m0 3a5 5 0 0 1 4 5v1" /></>,
    methodology: <><path d="M6 3h9l4 4v14H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /><path d="M14 3v5h5M8 12h8M8 16h8" /></>,
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[view]}</svg>;
}

export function DashboardShell({ activeView, releaseKey, children }: {
  activeView: ViewKey;
  releaseKey: string;
  children: ReactNode;
}) {
  const page = pageCopy[activeView];
  return (
    <div className="app-shell" id="top">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="nav-rail" aria-label="GeoBiz navigation">
        <a className="brand" href="#overview" aria-label="GeoBiz home">
          <span className="brand-mark" aria-hidden="true">G</span>
          <span className="brand-name">GeoBiz</span>
        </a>
        <nav aria-label="Navigasi utama">
          {destinations.map(({ view, hash, label }) => (
            <a className={`nav-link ${activeView === view ? "active" : ""}`} href={hash} aria-current={activeView === view ? "page" : undefined} key={view}>
              <RailIcon view={view} />
              <span>{label}</span>
            </a>
          ))}
        </nav>
        <div className="rail-caption"><span className="status-dot" aria-hidden="true" /><span>LOCAL DATA</span></div>
      </aside>
      <div className="app-content">
        <header className="topbar">
          <div className="page-identity"><span>{page.eyebrow}</span><strong>{page.title}</strong><small>{page.description}</small></div>
          <div className="project-meta"><span className="status-dot" aria-hidden="true" /><span><strong>DKI Jakarta</strong><small>{releaseKey}</small></span></div>
        </header>
        {children}
      </div>
    </div>
  );
}
