# GeoBiz Dashboard Polish and Feature Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring GeoBiz's existing dashboard materially closer to the approved Nixtio/Qala visual direction while fixing confirmed business-layer truncation and stale analysis, then audit the existing journeys.

**Architecture:** Keep the current React view modules and MapLibre map. Add offset pagination at the business endpoint and load complete category pages before calling the map layer complete; clear selection-dependent analysis as soon as its tuple changes. Extract a small shared navigation shell and map-control component, then consolidate the sage CSS and verify all four views at desktop, tablet, and phone widths.

**Tech Stack:** React, TypeScript, Vite, Vitest/Testing Library, MapLibre GL JS, FastAPI, SQLAlchemy/PostGIS, Playwright, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-07-geobiz-dashboard-polish-and-feature-audit-design.md`

## Global Constraints

- Coverage is DKI Jakarta; selectable categories are `fnb`, `retail`, and `services`. Healthcare is supporting evidence only.
- No fabricated demo businesses, demographics, counts, or financial widgets. Preserve OSM source identity and visible attribution.
- Keep local PMTiles, free online fallback, Docker Compose, and no paid API/key/account dependency.
- Preserve Map Explorer, Analytics, Demographics, Methodology, scoring semantics, on-demand refresh, and existing deep links.
- Do not alter the user-owned untracked `GeoBiz — Product Requirements Document.md`.
- Docker/Colima were off at planning time. Start them only for checks that require them, then stop services started for this task.

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/api/routes.py` | Add deterministic `offset` paging to `/api/businesses` without changing GeoJSON feature semantics. |
| `backend/tests/integration/test_api.py` | Verify page boundaries, ordering, and source identity. |
| `frontend/src/lib/api.ts` | Retrieve every business page, reject duplicate/non-advancing pages, surface partial-load failures. |
| `frontend/src/lib/api.test.ts` | Exercise multi-page, exact-boundary, duplicate-page, and network-failure cases. |
| `frontend/src/app/App.tsx` | Bind analysis to current controls; compose the new overview and shared shell. |
| `frontend/src/app/App.test.tsx` | Lock down pending/stale/error states and preserved navigation/overview workflows. |
| `frontend/src/components/DashboardShell.tsx` | Shared rail, header, skip link, deep-link navigation, and responsive labels. |
| `frontend/src/components/DashboardShell.test.tsx` | Verify destinations, active state, and main-content access. |
| `frontend/src/components/MapControls.tsx` | Search/category/radius plus expandable layer/filter controls and their labels. |
| `frontend/src/components/MapControls.test.tsx` | Verify retained choices, keyboard operability, and visible panel state. |
| `frontend/src/components/DemographicsView.tsx` | Keep SVG pointer selection but make labelled native select the explicit keyboard equivalent. |
| `frontend/src/components/ProductViews.test.tsx` | Verify demographic keyboard selection and resident-data wording. |
| `frontend/src/styles/index.css` | Consolidate one sage token system; desktop/tablet/mobile layout, focus, touch, map-panel styling. |
| `e2e/tests/map-explorer.spec.ts`, `e2e/tests/mobile.spec.ts`, `e2e/tests/offline.spec.ts` | Browser journeys, widths, and offline regression. |

## Review Focus

1. Exactly 1,000/2,000 business records, or an offset page with repeated IDs: client must finish complete sets and reject repeated pages instead of looping or labelling partial points complete (Task 1 tests).
2. Active data release changes between pages: client must reject mixed-release map data and ask for reload (Task 1 test).
3. Rapid category/radius changes and a failed latest request: no old score, metric, evidence, or area name appears under the new controls (Task 2 test).
4. A long location/business name at 390 px: controls and cards wrap/truncate locally without page-level horizontal overflow (Task 4 E2E).
5. Keyboard-only user and unavailable tile server: demographic selection still works and analysis remains reachable despite map failure (Task 5 tests/E2E).

---

### Task 1: Complete, deterministic business paging

**Files:** Modify `backend/app/api/routes.py`, `backend/tests/integration/test_api.py`, `frontend/src/lib/api.ts`, `frontend/src/app/App.tsx`; create `frontend/src/lib/api.test.ts`.

**Interfaces:** `/api/businesses?category=fnb&limit=1000&offset=1000&expected_release_id=2` returns the existing GeoJSON collection for a deterministic ID slice, or HTTP 409 if the active release changed. `fetchBusinesses(category: BusinessCategory, expectedReleaseId: number): Promise<BusinessFeature[]>` returns all pages or rejects without returning a partial set.

- [ ] **Step 1: Add the failing backend page-boundary test.** In `test_api.py`, use `_activate_v2`, insert three source-traceable F&B rows in ID order through the existing `db_session`/`dataset_sources` pattern, then assert the first `limit=2&offset=0` request has the first two source IDs and `limit=2&offset=2` has the third. Also assert `offset=-1` is HTTP 422 and a wrong `expected_release_id` is HTTP 409. The central assertion is:

  ```python
  first = client.get("/api/businesses", params={"category": "fnb", "limit": 2, "offset": 0})
  second = client.get("/api/businesses", params={"category": "fnb", "limit": 2, "offset": 2})
  assert [feature["id"] for feature in first.json()["features"]] == sorted(
      feature["id"] for feature in first.json()["features"]
  )
  assert set(feature["id"] for feature in first.json()["features"]).isdisjoint(
      feature["id"] for feature in second.json()["features"]
  )
  assert client.get("/api/businesses", params={"offset": -1}).status_code == 422
  assert client.get("/api/businesses", params={"expected_release_id": -1}).status_code == 409
  ```

- [ ] **Step 2: Run the specific backend test and see it fail.** Run `docker compose run --rm backend pytest -q tests/integration/test_api.py -k business`. Expected: the second page repeats the first records or the negative offset is not rejected.

- [ ] **Step 3: Implement backend paging.** Add `offset: Annotated[int, Query(ge=0)] = 0` and `expected_release_id: int | None = None` to `list_businesses`; reject a mismatched release with the existing `RELEASE_CHANGED` HTTP 409 pattern from `population_layer`; append `OFFSET :offset` after `LIMIT :limit`, and include `"offset": offset` in SQL parameters. Preserve `ORDER BY business.id`, the active-release predicate, category/bbox filters, and attribution.

  ```python
  limit: Annotated[int, Query(ge=1, le=5000)] = 3000,
  offset: Annotated[int, Query(ge=0)] = 0,
  expected_release_id: int | None = None,
  # SQL: ORDER BY business.id LIMIT :limit OFFSET :offset
  ```

- [ ] **Step 4: Add failing client paging tests.** In `api.test.ts`, mock `fetch` so offsets `0` and `1000` return distinct 1,000-feature pages, offset `2000` returns `[]`; assert exactly 2,000 unique IDs and three calls. Add separate tests where page two repeats IDs, returns HTTP 503, or returns HTTP 409 `RELEASE_CHANGED`; all must reject without a partial result. Keep test fixtures synthetic inside tests only.

  ```ts
  const features = await fetchBusinesses("fnb", 2);
  expect(new Set(features.map((item) => item.id)).size).toBe(2000);
  expect(vi.mocked(fetch).mock.calls.map(([url]) => String(url))).toEqual([
    "/api/businesses?category=fnb&limit=1000&offset=0&expected_release_id=2",
    "/api/businesses?category=fnb&limit=1000&offset=1000&expected_release_id=2",
    "/api/businesses?category=fnb&limit=1000&offset=2000&expected_release_id=2",
  ]);
  ```

- [ ] **Step 5: Implement complete client loading and an honest error state.** In `fetchBusinesses`, use `PAGE_SIZE = 1000`, append pages until a page is shorter than 1,000, throw on a repeated ID or after 100 pages, and return only after the terminating page. Pass `mapConfig.release_id` in every page request. In `App`, add `businessError`, `businessLoading`, and a retry nonce; on failure keep `businesses=[]` and show a retry action/status near the map and business table. Never show `categoryCount` as the number loaded on the map while loading/failing.

  ```ts
  const all: BusinessFeature[] = [];
  const seen = new Set<number>();
  for (let offset = 0; offset < 100_000; offset += 1000) {
    const page = await request<{ features: BusinessFeature[] }>(
      `/businesses?category=${category}&limit=1000&offset=${offset}&expected_release_id=${expectedReleaseId}`,
    );
    for (const feature of page.features) {
      if (seen.has(feature.id)) throw new Error("Business data page repeated an ID.");
      seen.add(feature.id);
      all.push(feature);
    }
    if (page.features.length < 1000) return all;
  }
  throw new Error("Business layer exceeded the safe page limit.");
  ```

- [ ] **Step 6: Run targeted tests and commit.** Run `npm test -- --run src/lib/api.test.ts src/app/App.test.tsx` in `frontend`, and the backend test above with Docker; both must pass. Commit only Task 1 files with `fix: load complete business layers`.

### Task 2: Keep analysis data attached to its selection

**Files:** Modify `frontend/src/app/App.tsx`, `frontend/src/app/App.test.tsx`.

**Interfaces:** The active selection is `{releaseId, category, radius, latitude, longitude}`; all score, metric, factor, density, evidence, and area-name content renders only for the current successful analysis. Existing `analyzeLocation` signature is unchanged.

- [ ] **Step 1: Write a failing test with a deferred second response.** Render `App` with the first analysis resolved; change Radius from 1 km to 2 km while holding the second `/analyze-location` promise. Assert the new radius is selected, the loading status is present, and old values such as `1,093.87`/`GAMBIR`/competitor count are absent from analysis-dependent UI. Resolve the second response and assert its new values appear. Repeat with a rejected second response and verify old evidence remains absent and retry is available.

  ```ts
  fireEvent.change(screen.getByLabelText("Radius"), { target: { value: "2000" } });
  expect(screen.getByText(/Menghitung faktor spasial/)).toBeVisible();
  expect(screen.queryByText("GAMBIR")).not.toBeInTheDocument();
  expect(screen.queryByText("1.093,87")).not.toBeInTheDocument();
  ```

- [ ] **Step 2: Run `npm test -- --run src/app/App.test.tsx` and see the stale-data assertion fail.**
- [ ] **Step 3: Implement selection-bound rendering.** Store the result together with a key built from release ID, category, radius, latitude, and longitude. Derive visible `analysis` only when its key matches the current selection; this prevents a one-frame stale flash before the effect runs. Keep the existing `cancelled` response guard and clear stored analysis at request start/failure. Render the map hint area, metric card, factor card, density card, nearby evidence, and methodology fingerprints from the derived `analysis`. Show `—` or a concise pending state for dependent values, and use `aria-live="polite"` for the analysis result region. Clear `focusedBusiness` on category changes so old-category inspection cannot persist in the new layer.

  ```ts
  const selectionKey = JSON.stringify([mapConfig?.release_id, category, radius, location.latitude, location.longitude]);
  const [analysisResult, setAnalysisResult] = useState<{ key: string; value: Analysis } | null>(null);
  const analysis = analysisResult?.key === selectionKey ? analysisResult.value : null;
  // Inside the existing effect:
  setLoading(true);
  setError(null);
  setAnalysisResult(null);
  analyzeLocation({ ...location, category, radius })
    .then((result) => { if (!cancelled) setAnalysisResult({ key: selectionKey, value: result }); });
  ```

- [ ] **Step 4: Pass the delayed-response, rejected-response, and existing stale-ranking tests.** Run `npm test -- --run src/app/App.test.tsx`; commit Task 2 files with `fix: prevent stale location analysis cards`.

### Task 3: Shared Nixtio-style dashboard shell

**Files:** Create `frontend/src/components/DashboardShell.tsx`, `frontend/src/components/DashboardShell.test.tsx`; modify `frontend/src/app/App.tsx`, `frontend/src/styles/index.css`.

**Interfaces:** `DashboardShell({activeView, releaseKey, children}: {activeView: ViewKey; releaseKey: string; children: ReactNode})`. Export `ViewKey` from `DashboardShell` so `App` and shell share one union. Existing hashes remain `#overview`, `#analytics`, `#demographics`, and `#methodology-view`.

- [ ] **Step 1: Write failing shell tests.** Assert four named links with correct hashes, active item has `aria-current="page"`, a `Skip to main content` link targets `#main-content`, and the release/context text names DKI Jakarta without claiming all sources are currently verified.

  ```tsx
  render(<DashboardShell activeView="demographics" releaseKey="release-test"><main id="main-content">Content</main></DashboardShell>);
  expect(screen.getByRole("link", { name: "Demographics" })).toHaveAttribute("href", "#demographics");
  expect(screen.getByRole("link", { name: "Demographics" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: /skip to main content/i })).toHaveAttribute("href", "#main-content");
  ```

- [ ] **Step 2: Run `npm test -- --run src/components/DashboardShell.test.tsx` and see the missing-component failure.**
- [ ] **Step 3: Implement `DashboardShell` and compose it in `App`.** Use `<aside className="nav-rail">` with `<nav>` and real anchors; one main page header inside the content frame; semantic labels for all rail destinations; preserve the existing `hashchange` handling and one `<main id="main-content">` per active view. Do not render fabricated user/profile, finance, or notification controls.

  ```tsx
  const destinations = [
    ["overview", "#overview", "Map Explorer"],
    ["analytics", "#analytics", "Analytics"],
    ["demographics", "#demographics", "Demographics"],
    ["methodology", "#methodology-view", "Methodology"],
  ] as const;
  <a href={hash} aria-current={activeView === key ? "page" : undefined}>{label}</a>
  ```

- [ ] **Step 4: Consolidate CSS into one sage system.** Remove superseded blue defaults/late overrides for the shell and common cards. Define the shared tokens once; style a 72–88 px desktop rail, restrained header, off-white cards, forest text, green accents, 14–16 px functional text, visible `:focus-visible`, and explicit hover/focus transitions. Keep map attribution readable. Avoid `transition: all` and do not suppress zoom.

  ```css
  :root { --canvas: #ebeee7; --surface: #fbfcf9; --ink: #2c3b27; --accent: #3c7048; --leaf: #6d9f62; --line: #dfe8dc; }
  .app-shell { display: grid; grid-template-columns: 78px minmax(0, 1fr); background: var(--surface); }
  .nav-rail { display: flex; flex-direction: column; border-right: 1px solid var(--line); }
  .nav-rail a:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  ```

- [ ] **Step 5: Run shell/App tests, typecheck, and commit.** Run `npm test -- --run src/components/DashboardShell.test.tsx src/app/App.test.tsx` and `npm run typecheck`; commit Task 3 files with `feat: add shared GeoBiz dashboard rail`.

### Task 4: Overview layout and unobstructed map controls

**Files:** Create `frontend/src/components/MapControls.tsx`, `frontend/src/components/MapControls.test.tsx`; modify `frontend/src/app/App.tsx`, `frontend/src/styles/index.css`, `e2e/tests/map-explorer.spec.ts`, `e2e/tests/mobile.spec.ts`.

**Interfaces:** Export `LayerKey = "opportunity" | "competitors" | "heatmap" | "population" | "transport" | "commercial" | "education" | "office" | "roads"` and `LayerState = Record<LayerKey, boolean>` from `MapControls`. `MapControlsProps` is `{category: BusinessCategory; radius: number; layers: LayerState; minimumScore: number; maximumCompetition: number | null; minimumPopulation: number; visibleAreas: number; onSelectLocation: (longitude: number, latitude: number) => void; onCategoryChange: (value: BusinessCategory) => void; onRadiusChange: (value: number) => void; onLayersChange: (value: LayerState) => void; onMinimumScoreChange: (value: number) => void; onMaximumCompetitionChange: (value: number | null) => void; onMinimumPopulationChange: (value: number) => void}`. It renders the existing `SearchBox` and labelled category/radius selects plus two native `<details>` panels. The `GeoMap` props and analysis API do not change.

- [ ] **Step 1: Add failing control tests.** Assert search/category/radius are visible, layer/filter options are absent from the visual flow until their respective `summary` is activated, toggles call their callbacks, and selections remain checked after close/reopen. Verify `Enter` on the focused summary opens each panel.

  ```tsx
  fireEvent.click(screen.getByText("Layers"));
  fireEvent.click(screen.getByLabelText("Population"));
  expect(onLayersChange).toHaveBeenCalledWith(expect.objectContaining({ population: true }));
  fireEvent.click(screen.getByText("Layers"));
  fireEvent.click(screen.getByText("Layers"));
  expect(screen.getByLabelText("Population")).toBeChecked();
  ```

- [ ] **Step 2: Run `npm test -- --run src/components/MapControls.test.tsx` and see the missing-component failure.**
- [ ] **Step 3: Implement the control component and overview composition.** Move the existing search/select JSX and panel contents out of `App` into `MapControls`. Keep the same layer keys, score/competition/population filters, and `filteredOpportunityAreas` logic. Position open panels under the toolbar, not permanently on top of the map; keep the small contextual legend when opportunity fill is on. Put a concise selected-location/score/candidate stack in the left insight column and the map in the right workspace. Retain full ranking/comparison and real-business table below the primary grid; convert their pseudo-table structure to semantic `<table>` markup where feasible, or add complete row/cell semantics.

  ```tsx
  <details className="toolbar-panel">
    <summary>Layers</summary>
    <div className="toolbar-panel-content">
      <label><input type="checkbox" checked={layers.population} onChange={() => onLayersChange({ ...layers, population: !layers.population })} />Population</label>
    </div>
  </details>
  <details className="toolbar-panel">
    <summary>Filters</summary>
    <div className="toolbar-panel-content">
      <label>Minimum score<select value={minimumScore} onChange={(event) => onMinimumScoreChange(Number(event.target.value))}><option value="0">All scores</option><option value="40">40+</option><option value="60">60+</option><option value="80">80+</option></select></label>
    </div>
  </details>
  ```

- [ ] **Step 4: Add responsive layout rules and browser assertions.** Use desktop `grid-template-columns: minmax(330px, 370px) minmax(0, 1fr)` inside the content frame; stack at tablet/phone widths; keep the map at least 420 px tall on phone; confine wide ranking tables to their own scroll container. In E2E, assert no page-level overflow at 1440×900, 768×1024, and 390×844 and verify a long search result/business name does not push the page sideways.

  ```ts
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  ```

- [ ] **Step 5: Run component tests, typecheck, and the affected E2E specs; commit.** Run `npm test -- --run src/components/MapControls.test.tsx src/app/App.test.tsx`, `npm run typecheck`, and `docker compose run --rm e2e npx playwright test tests/map-explorer.spec.ts tests/mobile.spec.ts`. Commit Task 4 files with `feat: polish map explorer layout and controls`.

### Task 5: Demographics accessibility and full-journey audit

**Files:** Modify `frontend/src/components/DemographicsView.tsx`, `frontend/src/components/ProductViews.test.tsx`, `frontend/src/styles/index.css`, `e2e/tests/offline.spec.ts`, `e2e/tests/recovery.spec.ts`; inspect all current view/E2E files without unrelated rewrites.

**Interfaces:** The native `#demographic-area-select` is the documented keyboard path for selecting a kelurahan. SVG paths/markers remain mouse-clickable visual controls but are hidden as a composite image from the accessibility tree; details are announced in the selected-area region.

- [ ] **Step 1: Add failing demographic keyboard test.** Focus the labelled `Kelurahan` select, change it by keyboard/input event to the fixture area, and assert the resident count/density detail appears in the `aria-live` region. Assert the map instructions explicitly mention the list as an alternative and still call it resident population, not customer demographic data.

  ```tsx
  const select = await screen.findByLabelText("Kelurahan");
  fireEvent.change(select, { target: { value: "1" } });
  expect(screen.getByText(/100 penduduk/)).toBeVisible();
  expect(screen.getByText(/gunakan daftar Kelurahan dengan keyboard/)).toBeInTheDocument();
  ```

- [ ] **Step 2: Run `npm test -- --run src/components/ProductViews.test.tsx` and confirm the new assertion fails before the adjustment.**
- [ ] **Step 3: Make the SVG/native-select relationship explicit.** Put `aria-hidden="true"` on the map SVGs, keep pointer click selection, retain the visible `Kelurahan` label and `aria-live="polite"` selected detail, and add concise helper text that the list is the keyboard alternative. Do not fabricate missing demographic values.

  ```tsx
  <svg className="demographics-map" viewBox="0 0 640 430" aria-hidden="true">
    {primaryAreas.map((area) => {
      const path = primaryMap.paths.get(area.id);
      return path ? renderArea(area, path) : null;
    })}
  </svg>
  <p className="selection-help">Pilih wilayah pada peta, atau gunakan daftar Kelurahan dengan keyboard.</p>
  ```

- [ ] **Step 4: Run browser feature audit.** Exercise navigation/hash links, local search, category/radius, map selection, layers, filters, ranking/comparison, business inspection, Analytics, Demographics, Methodology, loading/error/retry, and offline fallback. Add assertions to existing E2E specs for any reproducible defect found; fix only defects inside the approved existing journeys, and record separate data-pipeline/security issues for later approval. Capture/review screenshots at the three target viewport sizes against the supplied design references; do not accept a screenshot solely because tests pass.
- [ ] **Step 5: Run all checks, clean up, and commit.** Run `make test`, `make lint`, `make build-frontend`, and `make e2e` with Docker available; inspect warnings and bundle-size changes, remove temporary artifacts, then `docker compose down` and stop only Colima/services started for this verification. Verify `git status` does not include the untracked user PRD. Commit Task 5 files with `test: audit responsive and offline GeoBiz journeys` and report any unverified check honestly.

## Final review

Compare the completed branch with the spec: no capability removed, no fictional business data, complete point loading, no stale result under new controls, map visibly dominant, and Qala-inspired resident demographics. Review the whole diff, test evidence, browser screenshots, and Docker-off state. Do not push unless the user explicitly asks in this implementation cycle.
