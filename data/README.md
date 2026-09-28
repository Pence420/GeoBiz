# GeoBiz data workspace

GeoBiz demo data must come from traceable real-world sources. Raw and processed artifacts are intentionally ignored by Git because they can be large and are reproducible from the committed query and manifest metadata.

Rules:

- Never add invented businesses, names, coordinates, or competitor counts.
- Save raw downloads under `data/raw/`.
- Commit the source URL, query, retrieval time, source snapshot time, licence, checksum, and aggregate quality report under `data/manifests/`.
- Keep OpenStreetMap attribution visible in the application: `© OpenStreetMap contributors`.
- Test-only synthetic fixtures belong under `backend/tests/fixtures/` and must never be promoted to the demo database.

The initial OSM business snapshot is reproduced with `data/queries/dki-businesses.overpassql`. Public Overpass servers are used only for offline imports, never for user requests.

