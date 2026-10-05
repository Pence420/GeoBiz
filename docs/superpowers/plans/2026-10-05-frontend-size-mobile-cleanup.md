# Frontend Size, Mobile QA, and Local Cleanup Implementation Plan

> **For agentic workers:** Execute this plan natively in the current checkout. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the initial GeoBiz frontend bundle, make the public interface reliable at a 390×844 viewport, and remove only unreferenced generated artifacts.

**Architecture:** Keep the offline MapLibre/PMTiles path intact while moving non-default views behind React lazy boundaries and stable build chunks. Exercise the app through Playwright at the browser seam, then validate release references before deleting exact local artifact paths.

**Tech Stack:** React, TypeScript, Vite, MapLibre GL, PMTiles, Playwright, Docker Compose

**Spec:** User-approved bounded design in this task: optimize frontend size, test mobile display, and clean unused local artifacts while preserving active and rollback data.

## Global Constraints

- No paid or externally hosted runtime services.
- Preserve the active release and its immediate rollback release.
- Preserve the untracked Product Requirements Document.
- Mobile acceptance viewport is 390×844 CSS pixels.
- Tests observe only the public browser interface.

## Review Focus

- Narrow viewport: the page must not create document-level horizontal overflow.
- Map overlays: controls visible at the top of the map must not cover each other.
- Navigation: Map explorer, Analytics, and Methodology remain usable on mobile.
- Offline bundle: optimization must not introduce CDN or internet dependencies.
- Cleanup: no active, rollback, or database-referenced tile may be removed.

---

### Task 1: Mobile browser acceptance

**Files:**
- Create: `e2e/tests/mobile.spec.ts`
- Modify: `e2e/playwright.config.ts`
- Modify if required by the failing test: `frontend/src/styles/index.css`

**Interfaces:**
- Consumes: the public GeoBiz browser UI at `/`, `#analytics`, and `#methodology-view`.
- Produces: a dedicated `mobile-chromium` Playwright project at 390×844.

- [x] Write a mobile browser test covering overflow, map overlays, and navigation.
- [x] Run the test and confirm it exposes the existing mobile defect.
- [x] Apply the smallest responsive CSS change that fixes the defect.
- [x] Run the mobile test until it passes.

### Task 2: Initial bundle optimization

**Files:**
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/vite.config.ts`

**Interfaces:**
- Consumes: existing view components and browser hash navigation.
- Produces: lazy Analytics/Methodology chunks plus stable React and geospatial vendor chunks.

- [x] Capture the current production asset sizes.
- [x] Lazy-load non-default views behind a shared loading boundary.
- [x] Configure stable vendor chunk boundaries without adding a network dependency.
- [x] Run unit tests, type checking, and the production build; compare the entry asset.

### Task 3: Verified local artifact cleanup

**Files:**
- Delete only exact ignored/generated paths proven unreferenced.

**Interfaces:**
- Consumes: database release metadata and local release filenames.
- Produces: a smaller local workspace with active and immediate rollback artifacts intact.

- [x] Query release metadata and record active/rollback tile names.
- [x] Remove the failed-release workspace/tile and unreferenced legacy tile only after the query.
- [x] Remove build, browser-report, and language/tool caches.
- [x] Re-check retained tile files and Git status.

### Task 4: Full verification

**Files:**
- No product files beyond fixes required by a failing acceptance test.

**Interfaces:**
- Consumes: Compose application and all automated test suites.
- Produces: evidence for frontend unit/build checks and desktop/mobile browser flows.

- [x] Run frontend tests, lint/typecheck, and build.
- [x] Run desktop and mobile Playwright suites.
- [x] Confirm no external requests are required for the offline map.
- [x] Report bundle deltas and reclaimed local space.
