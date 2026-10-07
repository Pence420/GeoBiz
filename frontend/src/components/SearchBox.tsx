import { useEffect, useRef, useState } from "react";

import { searchLocations, type SearchResult } from "../lib/api";

type Props = {
  onSelect: (longitude: number, latitude: number) => void;
};

export function SearchBox({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "empty" | "error">("idle");
  const requestId = useRef(0);
  const selectedQuery = useRef<string | null>(null);

  useEffect(() => {
    const currentRequest = ++requestId.current;
    if (query === selectedQuery.current) {
      setResults([]);
      setStatus("idle");
      return;
    }
    if (query.trim().length < 2) {
      setResults([]);
      setStatus("idle");
      return;
    }
    const timeout = window.setTimeout(() => {
      setStatus("loading");
      searchLocations(query.trim())
        .then((items) => {
          if (currentRequest !== requestId.current) return;
          setResults(items);
          setStatus(items.length ? "idle" : "empty");
        })
        .catch(() => {
          if (currentRequest !== requestId.current) return;
          setResults([]);
          setStatus("error");
        });
    }, 220);
    return () => window.clearTimeout(timeout);
  }, [query]);

  const choose = (result: SearchResult) => {
    selectedQuery.current = result.name;
    setQuery(result.name);
    setResults([]);
    onSelect(result.longitude, result.latitude);
  };

  return (
    <div className="search-box">
      <span className="search-icon" aria-hidden="true">⌕</span>
      <label>
        <span className="sr-only">Search district, business, landmark, or coordinate</span>
        <input
          name="location-search"
          value={query}
          onChange={(event) => {
            selectedQuery.current = null;
            setQuery(event.target.value);
          }}
          placeholder="Search Senayan or -6.22, 106.80…"
          autoComplete="off"
        />
      </label>
      {query.length > 0 ? (
        <button type="button" aria-label="Clear search" onClick={() => {
          selectedQuery.current = null;
          setQuery("");
        }}>×</button>
      ) : null}
      {results.length > 0 || status !== "idle" ? (
        <div className="search-results" role="listbox" aria-label="Search results" aria-live="polite">
          {results.map((result) => (
            <button type="button" role="option" aria-selected="false" key={result.id} onClick={() => choose(result)}>
              <span>{result.name}</span>
              <small>{result.subtitle}{result.source_record_id ? ` · source ${result.source_record_id}` : ""}</small>
            </button>
          ))}
          {status === "loading" ? <p>Searching local DKI data…</p> : null}
          {status === "empty" ? <p>No local match. Click the map to choose a location.</p> : null}
          {status === "error" ? <p>Search unavailable. Click the map to choose a location.</p> : null}
        </div>
      ) : null}
    </div>
  );
}
