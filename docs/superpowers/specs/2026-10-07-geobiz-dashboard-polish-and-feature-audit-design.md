# GeoBiz Dashboard Polish and Feature Audit — Design Specification

**Date:** 2026-10-07

**Status:** Proposed for user review

**Scope:** Existing React dashboard, its map/business-list API seam, and regression coverage

## 1. Intent and success criteria

GeoBiz should look and feel substantially closer to the user's [Nixtio property dashboard reference](https://dribbble.com/shots/26833717-Property-Web-Dashboard-Design): a quiet sage canvas, slim navigation rail, compact command area, restrained information cards, and a large, unobstructed map. The Demographics tab should retain the compact chart/map rhythm inspired by the [Qala demographics reference](https://dribbble.com/shots/26889413-Location-Intelligence-Demographics-Dashboard), but represent **residents of DKI administrative areas**, not visitors or customers. This is a translation of the references into GeoBiz's own product and data, not a copy of their branding, imagery, or fictional metrics.

Success means the dashboard is easier to scan at desktop and mobile sizes, existing workflows still work, and the confirmed data/state bugs are fixed with automated regressions. The UI must never imply that a location score guarantees business success.

## 2. Fixed product constraints

- Geography: DKI Jakarta. Selectable umbrella categories: F&B, Retail, Services. Healthcare remains supporting location evidence, not a selectable business category.
- Displayed business records and competitor evidence must be real, source-traceable OSM records. No fabricated demo businesses, counts, demographics, or revenue-style widgets.
- Keep the existing MapLibre + local PMTiles basemap and visible OSM attribution; retain the free online fallback. No paid API, billing account, map key, or new hosted dependency.
- Keep Docker Compose as the supported demo runtime. This redesign does not change scoring formulas, source refresh cadence, or the active data release.
- Preserve Map Explorer, Analytics, Demographics, and Methodology and all existing substantive controls. The redesign may change where a control lives, not silently remove its capability.
- Do not add authentication, user profiles, financial KPIs, or a new component framework solely for visual parity.

## 3. Chosen approach and alternatives

The selected approach is a **targeted shell and overview re-layout** using existing React components and design tokens. Pure CSS recoloring would leave the top navigation and permanent map overlays unlike the reference. A complete frontend rewrite would add unnecessary regression risk to working data and map flows. The chosen approach changes component composition where needed but retains the typed API client, MapLibre map, and existing view boundaries.

## 4. Information architecture and visual design

### 4.1 Shared shell

- At wide widths, a narrow persistent left rail carries the GeoBiz mark and four labelled destinations: Map Explorer, Analytics, Demographics, Methodology. The active destination is unmistakable through both shape/background and text, not color alone.
- The main canvas has a compact page header with view title, a concise DKI/data-release context, and no fake profile or notification controls.
- Use one token system rather than the current blue base CSS plus a second sage override block. Target palette derives from the Nixtio reference: pale sage outer canvas (`#EBEEE7` family), warm off-white cards, deep forest text (`#2C3B27` family), and muted green accents. Preserve sufficient text/control contrast.
- Typography uses a clear 3-level hierarchy: page title, card title, and supporting metadata. Replace 8–10 px functional text with readable sizes; keep tabular numerals for scores and counts. Borders and shadow are quiet and consistent, with rounded corners used systematically.
- Navigation remains deep-linkable with the existing hash routes. The skip link and one main landmark per view remain intact.

### 4.2 Map Explorer composition

- Desktop content is a two-column grid: approximately 330–380 px insight/candidate column on the left and the dominant map workspace on the right. The map should occupy the majority of the usable width at 1440 px without a permanent control panel covering it.
- The left column starts with the selected location score, an honest status/freshness cue, and a compact set of key area signals. Factor breakdown and nearby evidence remain available below. The first few ranked opportunity areas may be shown as concise actionable cards; the full ranking, comparison, and real-business table remain accessible farther down the page.
- Search, category, and radius sit in one compact toolbar above the map. Layer toggles and opportunity filters move to labelled popovers/drawers opened by buttons. Each panel has a clear close path and keeps its selections when closed. The opportunity legend remains visible only when relevant and takes minimal map space.
- Selected point, analysis radius, OSM businesses/clusters, opportunity fill, other toggled layers, map attribution, zoom/fullscreen/reset, and online/offline status continue to work. Do not cover important map controls with cards or drawers.
- A category or radius change updates the map, ranking, count, analysis, and context labels as one coherent state; pending results are marked as loading rather than displaying old values under new labels.

### 4.3 Other views

- Analytics and Methodology inherit the new rail, header, spacing, typography, and card tokens without changing their underlying meaning.
- Demographics keeps its resident-population summary, age/gender chart, area selection, provenance, and population-density map. Its arrangement should feel like Qala's compact chart-plus-map view while explicitly saying these are administrative-area residents. No visitor/returning-customer widgets are introduced.

### 4.4 Responsive behavior

- At tablet widths the rail becomes compact and the map/insight grid stacks without horizontal page overflow. At phone widths navigation becomes a concise accessible top or bottom control; no hidden icon-only navigation without labels.
- Search and selectors remain usable at 390 px. Map tools are reachable with touch, and the map retains enough height for inspection. Tables can scroll within their own region; the whole page should not scroll sideways.
- Test at least 1440×900, 768×1024, and 390×844. Respect reduced-motion preferences and visible keyboard focus.

## 5. Feature audit and confirmed defects

The audit covers navigation/deep links, search, category/radius changes, map selection and inspection, layer toggles, opportunity filters, rankings/comparison, real-business list, Analytics, Demographics, Methodology, loading/error/retry, offline map fallback, and mobile interaction. Findings are classified as reproducible bug, usability/accessibility defect, or out-of-scope observation. A visual change must not be used to hide a broken workflow.

### 5.1 Business layer silently truncates

The current client requests `/businesses?...&limit=3000`, while the active F&B category count was observed at 3,415. The map/heatmap therefore cannot represent all counted F&B records. Change the API/client seam to fetch complete category data safely—prefer deterministic pagination with a total/continuation signal, or an equivalent bounded strategy that cannot silently truncate. Keep the map's clustering behavior and show a visible failure/incomplete state if full data cannot be loaded. Test a fixture exceeding one page and verify the rendered layer receives all records without duplicates.

### 5.2 Old analysis shown under new controls

The score card has a loading state, but Area signals, factor breakdown, population density, nearby evidence, and map hint can still read the prior `analysis` while category/radius/location already show new values. Bind displayed analysis to its request parameters and active release, or clear/hide all dependent values at request start. Ignore stale responses after a newer selection. Add a delayed-response regression covering rapid radius/category changes and error/retry.

### 5.3 Accessibility and interaction audit targets

- The Demographics SVG areas are pointer-clickable; provide keyboard-operable area selection or make the existing select the clearly documented equivalent without presenting SVG shapes as the sole interaction.
- Replace pseudo-tables with semantic tables where tabular relationships matter, or complete their ARIA row/cell semantics. Search suggestions must have a coherent keyboard and focus pattern.
- Label icon-only controls, announce async states where useful, preserve focus visibility, and ensure popovers/drawers can be closed by keyboard. Verify no overlay traps or obscures focused map controls.

The audit may identify more defects. In-scope defects in these existing user journeys are fixed with a focused regression. Issues requiring a new data source, scoring redesign, or independent backend security/data-pipeline project are documented separately for user approval rather than silently expanding this implementation.

## 6. Data and state flow

The overview has one selection tuple: `{releaseId, category, radius, longitude, latitude}`. Analysis responses are associated with the tuple that requested them; only a matching response may appear in dependent cards. Category business data is fetched completely for the active release/category before the map labels it complete. Opportunity rankings and map polygons follow the same category/radius pair. Layer visibility and opportunity filters are presentation state; they must not modify source counts or the scored analysis.

Use existing view modules (`App`, `GeoMap`, `AnalyticsView`, `DemographicsView`, `MethodologyView`) and the typed API client. Extract small shell/control components only when this reduces the current `App` complexity. Avoid creating a generic design-system package for this one dashboard.

## 7. Error and empty states

- Offline tile failure: keep analysis cards available, show a specific map recovery action, and retain attribution/fallback disclosure.
- Business page failure: do not present a partial point set as the complete category; show retry and the incomplete status.
- Analysis failure: clear dependent metrics for the failed selection and offer retry without reverting the user's chosen controls.
- Empty rankings/search/business results: show honest empty states, never sample or fabricated content.

## 8. Verification and acceptance

1. Component/integration tests reproduce both confirmed defects before fixes and pass after fixes; stale-request and paginated-business cases are covered.
2. Existing frontend/backend unit tests, lint/type checks, production build, and browser E2E pass. If Docker is unavailable, report which checks could not run; do not claim an unverified pass.
3. Browser E2E exercises the main journeys and at least one offline-map path; desktop/tablet/mobile screenshots are reviewed against the two supplied references for hierarchy, spacing, map prominence, and readability.
4. Keyboard-only navigation reaches tabs, search, map alternatives, filters, comparison, and demographic area selection; focus is visible. No page-level horizontal overflow at the target widths.
5. All displayed business records remain source-traceable. No paid network request or account/key requirement is introduced. The app remains portable through the documented Docker setup.

## 9. Out of scope

New business categories, fabricated demonstration data, demographics of customers/visitors, new scoring weights, scheduled refresh, hosted deployment, paid maps, and wholesale map-engine replacement are out of scope. Any separate release-integrity or infrastructure issue found by the audit will be recorded with severity and a proposed follow-up, unless it directly blocks a user journey above.
