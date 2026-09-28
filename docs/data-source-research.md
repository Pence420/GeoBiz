# GeoBiz DKI Jakarta — Data Source Research

Last reviewed: 2026-09-28

## Recommendation

> **Non-negotiable academic requirement:** every business shown on the map or used by the scoring engine must be a real-world business record traceable to its source. Synthetic businesses, invented names, randomly generated coordinates, and fabricated competitor counts are prohibited in production/demo data. Test fixtures may use synthetic records only inside automated tests and must never be loaded into the demo database.

Use a reproducible hybrid dataset rather than forcing every layer to come from one provider:

1. **Administrative boundaries:** BIG (Badan Informasi Geospasial), filtered to DKI Jakarta.
2. **Population:** Satu Data Jakarta/BPS at kelurahan level, joined to the BIG polygons by standardized region code where possible and normalized name as a fallback.
3. **Business competitors, supporting POIs, commercial activity, and roads:** an OpenStreetMap snapshot extracted through Overpass during development, then stored locally and imported into PostGIS.
4. **Public transport:** official TransJakarta GTFS for bus stops; supplement MRT/LRT/KRL stations from OSM only when they are absent from the official feed used by the project.

Every imported dataset should store `source`, `source_url`, `source_date`, `retrieved_at`, and (where available) `source_id`. The application should display a short data-attribution note and the analysis response should include the dataset snapshot date.

For OpenStreetMap businesses, retain the original OSM element type and ID (`node`, `way`, or `relation`) so each displayed record can be audited against its source. Records without a business name may contribute only when the methodology explicitly allows unnamed mapped facilities; they should not be presented to users as a named business.

This is a university-project dataset, not a claim that every operating business in Jakarta is present. The report and UI should explicitly state that OSM completeness varies by category and area.

## Source assessment

| Layer | Primary source | Format/access | Why use it | Caveats |
|---|---|---|---|---|
| Kelurahan boundaries | BIG Ina-Geoportal `ADMINISTRASI_AR_DESAKEL` | Geodatabase/download service, EPSG:4326 | National geospatial authority; includes desa/kelurahan geometries and standardized administrative context | The published metadata warns that boundaries are not definitive in every Indonesian region; filter and validate DKI geometry before use |
| Population | Satu Data Jakarta datasets, cross-checked against BPS DKI publications | Downloadable tabular data | Government data exists at kelurahan granularity, suitable for joining to polygons | Dataset years and schemas vary; freeze one clearly documented year rather than silently mixing years |
| Population QA/context | BPS DKI Jakarta, *DKI Jakarta Province in Figures* and kecamatan publications | XLS/PDF publication downloads | Authoritative statistical reference and useful for aggregate checks | Province/city totals alone are too coarse for point scoring |
| Restaurants | OpenStreetMap | Overpass snapshot: `amenity=restaurant` | Practical, geocoded, reproducible, and directly usable in PostGIS | Community-maintained and incomplete; names/tags can be inconsistent |
| Gyms | OpenStreetMap | `leisure=fitness_centre` | This is the documented de-facto OSM tag for gyms/fitness centres | Also inspect legacy/alternative tags during data QA; do not count outdoor `fitness_station` as a direct gym competitor |
| Pharmacies | OpenStreetMap | `amenity=pharmacy` and, during QA, `healthcare=pharmacy` | Practical competitor geometry | Deduplicate features carrying both tags and branches represented as both node and polygon |
| Offices | OpenStreetMap | `office=*`; optionally named office buildings | Provides points/polygons for an office-access proxy | Count/density is a proxy, not number of workers; avoid presenting it as employment data |
| Universities/schools | OpenStreetMap | `amenity=university`, `amenity=college`, `amenity=school` | Suitable customer-concentration proxy | Large campuses may be polygons; convert polygons to representative points only for proximity counts, while retaining original geometry |
| Commercial activity | OpenStreetMap | `landuse=commercial`, `landuse=retail`, `shop=*`, malls/marketplaces | Supports both area coverage and POI-density features | Avoid double counting a mall polygon and every shop inside it in the same factor |
| Healthcare support | OpenStreetMap | `amenity=clinic`, `amenity=hospital`, `healthcare=*` | Relevant to pharmacy scoring | Define which healthcare types contribute before extraction |
| Roads | OpenStreetMap | `highway=*` | Strongest practical open road network for the MVP | Road accessibility should use proximity to selected road classes, not raw segment count |
| Bus stops/routes | TransJakarta PPID GTFS Static | GTFS ZIP (`stops.txt`, routes, trips, etc.) | First-party operator feed, standardized and licensed CC BY 4.0 | Freeze and record the feed version; service changes over time |
| MRT/LRT/KRL stations | Operator/open-government feed if a stable downloadable source is confirmed; otherwise OSM | GTFS or OSM | Prevents transport analysis being limited to buses | Mark supplemental OSM transit records separately from official TransJakarta records |

## Primary-source evidence

- [Jakarta Satu](https://jakartasatu.jakarta.go.id/geoportal/tentang) describes itself as the public spatial-data integration portal for DKI Jakarta government units and states that its information is updated periodically.
- [Jakarta Satu spatial catalogue](https://jakartasatu.jakarta.go.id/apimobile/web) exposes a public catalogue of Jakarta spatial maps and data.
- [BIG `ADMINISTRASI_AR_DESAKEL`](https://tanahair.indonesia.go.id/sdi/dataset/administrasi_ar_desakel) documents the desa/kelurahan geodatabase, its EPSG:4326 spatial reference, revision lineage, and limitations.
- [Satu Data Indonesia — population by age per DKI kelurahan](https://data.go.id/dataset/dataset/data-jumlah-penduduk-berdasarkan-usia-per-kelurahan-dki-jakarta) confirms the availability of population distribution at kelurahan level from the DKI Jakarta organization.
- [BPS DKI Jakarta Province in Figures 2025](https://jakarta.bps.go.id/id/publication/2025/02/28/30874e042a98939928603ee5/dki-jakarta-province-in-figures-2025.html) is the annual statistical publication used for aggregate validation and context.
- [TransJakarta PPID](https://ppid.transjakarta.co.id/informasi/berkala) publishes its operating-service data as GTFS Static and labels it CC BY 4.0.
- The [official GTFS schedule reference](https://gtfs.org/documentation/schedule/reference/) defines `stops.txt`, routes, trips, stop times, and the required location fields used by the importer.
- [OpenStreetMap copyright and licence](https://www.openstreetmap.org/copyright) states that OSM data is available under ODbL and requires attribution to OpenStreetMap and its contributors.
- The OSM Foundation [API usage policy](https://operations.osmfoundation.org/policies/api/) identifies Overpass as a read-only data-access option and points bulk users toward extracts; therefore GeoBiz should not query public Overpass servers for every user request.
- The OSM tagging documentation identifies [`leisure=fitness_centre`](https://wiki.openstreetmap.org/wiki/Tag%3Aleisure%3Dfitness_centre) as the de-facto gym/fitness-centre tag.

## Extraction policy

The data import should be an offline ETL command, not part of the request-time API:

1. Download/fetch source data once.
2. Save the raw artifact or a checksum plus retrieval metadata.
3. Transform geometries to EPSG:4326 for storage and use PostGIS `geography` for metre-based proximity.
4. Clip all records to the chosen DKI Jakarta boundary.
5. Normalize category tags into GeoBiz's internal taxonomy.
6. Deduplicate OSM node/way/relation representations using OSM type and ID plus spatial/name checks.
7. Load staging tables, run validation, then promote to application tables.
8. Generate a data-quality summary: counts per category and city, null-name rate, invalid geometries, duplicate candidates, and snapshot dates.

Example internal mapping:

| GeoBiz type | Source filter |
|---|---|
| `restaurant` | `amenity=restaurant` |
| `gym` | `leisure=fitness_centre` |
| `pharmacy` | `amenity=pharmacy` OR `healthcare=pharmacy`, deduplicated |
| `university` | `amenity=university` OR `amenity=college` |
| `school` | `amenity=school` |
| `office` | `office=*` |
| `commercial_area` | `landuse=commercial` OR `landuse=retail` |
| `mall` | `shop=mall` |
| `market` | `amenity=marketplace` |
| `healthcare` | selected `amenity=hospital|clinic|doctors` and relevant `healthcare=*` values |

## Initial scoring model

### Unit of analysis

- **Clicked location:** compute features inside the user-selected radius (default 1 km).
- **Opportunity map:** compute the same model at each kelurahan centroid or on a regular hexagonal grid. A hex grid is methodologically fairer for ranking locations because kelurahan sizes differ; kelurahan polygons can still be used for population joins and presentation.

For the first MVP, clicked-location scoring plus a kelurahan choropleth is acceptable. Document that area scores represent their sampling point or aggregate, not every address within the polygon.

### Normalization

Do not use undocumented fixed thresholds such as “five restaurants = high.” For each business category and radius:

1. Create reference observations across DKI Jakarta (for example, equal-area hex-cell centroids).
2. Calculate every raw factor for every observation.
3. Winsorize values at the 5th and 95th percentiles to limit extreme outliers.
4. Convert to percentile rank from 0–100.
5. For negative factors such as competition, use `100 - percentile_rank`.

This produces an interpretable claim: a population score of 80 means the location is above roughly 80% of comparable sampled locations in DKI for that metric. Persist the normalization version and reference snapshot so the same input remains reproducible.

### Candidate weights

Weights are hypotheses for the academic MVP, not causal proof of business success. They should be editable in the database and clearly displayed in the methodology page.

| Factor | Restaurant | Gym | Pharmacy |
|---|---:|---:|---:|
| Population density | 20% | 30% | 25% |
| Low competition | 20% | 20% | 15% |
| Public transport access | 15% | 10% | 10% |
| Commercial activity | 15% | 10% | 10% |
| Office proximity/density | 20% | 15% | 5% |
| Road accessibility | 10% | 15% | 10% |
| Healthcare proximity | 0% | 0% | 25% |
| **Total** | **100%** | **100%** | **100%** |

University proximity can later replace part of the population/office weight for student-oriented restaurant concepts. For the initial three generic categories it should remain an insight, not a weighted factor, to keep the model understandable.

### Factor definitions for v1

- **Population:** kelurahan population density assigned by point-in-polygon. This is coarser than the other factors and must be labelled accordingly.
- **Competition:** weighted competitor count within radius, optionally using distance bands (closer competitors contribute more).
- **Transport:** distinct stations/stops within radius; cap multiple platforms belonging to the same station to prevent inflation.
- **Commercial:** a combined metric of commercial/retail land coverage and selected commercial POIs, normalized separately before combination.
- **Office:** office POI density; label it as an office-activity proxy.
- **Road:** distance to the nearest suitable primary/secondary/tertiary road plus the number of distinct accessible road classes; do not reward raw line density.
- **Healthcare (pharmacy):** clinics, hospitals, and doctors within radius, deduplicated by facility.

Final score:

```text
final_score = sum(normalized_factor_score * category_weight)
```

Suggested labels: `0–20 Very Low`, `>20–40 Low`, `>40–60 Moderate`, `>60–80 Good`, `>80–100 High`. These are presentation bands, not statistical confidence intervals.

## Risks and mitigations

- **OSM incompleteness:** show snapshot date, publish category counts, and mention that results support comparison rather than guaranteeing market reality.
- **Mixed years:** select one population vintage and expose it in metadata; never imply that all layers have the same observation date.
- **Name-based joins:** prefer official region codes. If only names exist, normalize case/punctuation and maintain a reviewed alias table.
- **Double counting:** deduplicate pharmacies with two tags, transit platforms belonging to one station, and POIs represented as both points and polygons.
- **False precision:** display rounded scores and a methodology drawer. Avoid claims such as “83% chance of success.”
- **Licensing:** keep visible `© OpenStreetMap contributors` attribution, retain ODbL source metadata, and attribute TransJakarta under CC BY 4.0.

## Implementation decision

Proceed with the hybrid strategy above. Before implementing the full ETL, run a small spike that downloads DKI Jakarta restaurant, gym, and pharmacy records; reports counts and missing-name rates; and verifies that a population table can be joined to at least 95% of kelurahan polygons. If that threshold is not reached, create and document a manual code/name crosswalk rather than silently dropping areas.
