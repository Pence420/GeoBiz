from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.contracts import (
    AnalysisCoverage,
    ContainingArea,
    LocationEvidence,
    NearbyBusiness,
    NearbyMetrics,
    NearbyRoad,
    NearbyTransport,
    PoiBreakdown,
)
from app.datasets.service import active_release_id


class SpatialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_containing_area(
        self, *, longitude: float, latitude: float
    ) -> ContainingArea | None:
        release_id = active_release_id(self.session)
        row = self.session.execute(
            text(
                """
                SELECT
                    area.id,
                    area.name,
                    area.official_code,
                    area.population_density::float,
                    area.area_type,
                    area.population,
                    area.observed_at AS population_observed_at,
                    area.original_properties ->> 'kecamatan' AS kecamatan,
                    (
                        SELECT coverage.official_code
                        FROM administrative_areas AS coverage
                        WHERE coverage.data_release_id = :release_id
                          AND coverage.official_code = 'ID-JK'
                          AND ST_Covers(
                              coverage.geom,
                              ST_SetSRID(ST_Point(:longitude, :latitude), 4326)
                          )
                        LIMIT 1
                    ) AS coverage_official_code
                FROM administrative_areas AS area
                WHERE area.data_release_id = :release_id
                  AND ST_Covers(
                    area.geom,
                    ST_SetSRID(ST_Point(:longitude, :latitude), 4326)
                )
                ORDER BY
                    CASE area.area_type
                        WHEN 'kelurahan' THEN 1
                        WHEN 'kecamatan' THEN 2
                        WHEN 'city' THEN 3
                        ELSE 4
                    END,
                    ST_Area(area.geom)
                LIMIT 1
                """
            ),
            {
                "longitude": longitude,
                "latitude": latitude,
                "release_id": release_id,
            },
        ).mappings().first()
        return ContainingArea(**row) if row else None

    def calculate_metrics(
        self,
        *,
        longitude: float,
        latitude: float,
        category_slug: str,
        radius_m: int,
    ) -> NearbyMetrics:
        parameters = {
            "longitude": longitude,
            "latitude": latitude,
            "category_slug": category_slug,
            "radius_m": radius_m,
            "release_id": active_release_id(self.session),
        }
        competitor_count = self.session.scalar(
            text(
                """
                SELECT count(*)
                FROM businesses AS business
                JOIN business_categories AS category
                  ON category.id = business.category_id
                WHERE category.slug = :category_slug
                  AND business.data_release_id = :release_id
                  AND ST_DWithin(
                      business.geom::geography,
                      ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                      :radius_m
                  )
                """
            ),
            parameters,
        )
        area = self.find_containing_area(longitude=longitude, latitude=latitude)
        return NearbyMetrics(
            competitor_count=int(competitor_count or 0),
            transport_stop_count=self._nearby_optional_count(
                "transport_stops", parameters, distinct_station=True
            ),
            commercial_poi_count=self._nearby_optional_count(
                "pois", parameters, poi_types=("commercial", "retail")
            ),
            office_count=self._nearby_optional_count(
                "pois", parameters, poi_types=("office",)
            ),
            university_count=self._nearby_optional_count(
                "pois", parameters, poi_types=("university", "college", "school")
            ),
            healthcare_count=self._nearby_optional_count(
                "pois", parameters, poi_types=("hospital", "clinic", "doctors")
            ),
            population_density=area.population_density if area else None,
            nearest_major_road_m=self._nearest_road_distance(parameters),
        )

    def detailed_evidence(
        self,
        *,
        longitude: float,
        latitude: float,
        category_slug: str,
        radius_m: int,
    ) -> LocationEvidence:
        parameters: dict[str, object] = {
            "longitude": longitude,
            "latitude": latitude,
            "category_slug": category_slug,
            "radius_m": radius_m,
            "release_id": active_release_id(self.session),
        }
        subtype_rows = self.session.execute(
            text(
                """
                SELECT business.business_subtype, count(*)::int AS record_count
                FROM businesses AS business
                JOIN business_categories AS category
                  ON category.id = business.category_id
                WHERE business.data_release_id = :release_id
                  AND category.slug = :category_slug
                  AND ST_DWithin(
                      business.geom::geography,
                      ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                      :radius_m
                  )
                GROUP BY business.business_subtype
                ORDER BY business.business_subtype
                """
            ),
            parameters,
        ).all()
        competitors = self.session.execute(
            text(
                """
                SELECT
                    business.name,
                    business.business_subtype,
                    ST_Distance(
                        business.geom::geography,
                        ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography
                    )::float AS distance_m,
                    ST_Y(business.geom) AS latitude,
                    ST_X(business.geom) AS longitude,
                    business.source_type,
                    business.source_record_id,
                    nullif(concat_ws(', ',
                        business.original_tags ->> 'addr:housenumber',
                        business.original_tags ->> 'addr:street',
                        business.original_tags ->> 'addr:suburb',
                        business.original_tags ->> 'addr:city'
                    ), '') AS address,
                    business.original_tags ->> 'brand' AS brand,
                    business.original_tags ->> 'operator' AS operator,
                    business.original_tags ->> 'opening_hours' AS opening_hours,
                    coalesce(
                        business.original_tags ->> 'contact:phone',
                        business.original_tags ->> 'phone'
                    ) AS phone,
                    coalesce(
                        business.original_tags ->> 'contact:website',
                        business.original_tags ->> 'website'
                    ) AS website
                FROM businesses AS business
                JOIN business_categories AS category
                  ON category.id = business.category_id
                WHERE business.data_release_id = :release_id
                  AND category.slug = :category_slug
                  AND ST_DWithin(
                      business.geom::geography,
                      ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                      :radius_m
                  )
                ORDER BY distance_m, business.id
                LIMIT 10
                """
            ),
            parameters,
        ).mappings().all()
        nearest_transport_row = self.session.execute(
            text(
                """
                SELECT
                    stop.name,
                    stop.transport_type,
                    ST_Distance(
                        stop.geom::geography,
                        ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography
                    )::float AS distance_m,
                    ST_Y(stop.geom) AS latitude,
                    ST_X(stop.geom) AS longitude,
                    stop.source_record_id
                FROM transport_stops AS stop
                WHERE stop.data_release_id = :release_id
                ORDER BY distance_m, stop.id
                LIMIT 1
                """
            ),
            parameters,
        ).mappings().first()
        nearest_road_row = self.session.execute(
            text(
                """
                SELECT
                    road.name,
                    road.road_type,
                    ST_Distance(
                        road.geom::geography,
                        ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography
                    )::float AS distance_m,
                    road.source_type,
                    road.source_record_id
                FROM roads AS road
                WHERE road.data_release_id = :release_id
                  AND road.road_type IN (
                      'motorway', 'motorway_link', 'trunk', 'trunk_link',
                      'primary', 'primary_link', 'secondary', 'secondary_link'
                  )
                ORDER BY distance_m, road.id
                LIMIT 1
                """
            ),
            parameters,
        ).mappings().first()
        poi_rows = self.session.execute(
            text(
                """
                SELECT
                    CASE
                        WHEN poi_type IN ('commercial', 'retail', 'marketplace', 'bank')
                            THEN 'commercial'
                        WHEN poi_type = 'office' THEN 'office'
                        WHEN poi_type IN ('university', 'college', 'school')
                            THEN 'education'
                        WHEN poi_type IN ('hospital', 'clinic', 'doctors')
                            THEN 'healthcare'
                    END AS evidence_group,
                    poi_type,
                    count(*)::int AS record_count
                FROM pois
                WHERE data_release_id = :release_id
                  AND ST_DWithin(
                      geom::geography,
                      ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                      :radius_m
                  )
                GROUP BY evidence_group, poi_type
                HAVING CASE
                    WHEN poi_type IN ('commercial', 'retail', 'marketplace', 'bank')
                        THEN 'commercial'
                    WHEN poi_type = 'office' THEN 'office'
                    WHEN poi_type IN ('university', 'college', 'school')
                        THEN 'education'
                    WHEN poi_type IN ('hospital', 'clinic', 'doctors')
                        THEN 'healthcare'
                END IS NOT NULL
                ORDER BY evidence_group, poi_type
                """
            ),
            parameters,
        ).mappings().all()
        coverage_row = self.session.execute(
            text(
                """
                SELECT
                    count(*)::int AS total_businesses,
                    coalesce(100.0 * count(business.name) / nullif(count(*), 0), 0)::float
                        AS named_business_percent,
                    (count(*) FILTER (WHERE business.original_tags ->> 'brand' IS NULL))::int
                        AS missing_brand,
                    (count(*) FILTER (WHERE business.original_tags ->> 'operator' IS NULL))::int
                        AS missing_operator,
                    (count(*) FILTER (WHERE business.original_tags ->> 'opening_hours' IS NULL))::int
                        AS missing_opening_hours,
                    (count(*) FILTER (WHERE coalesce(
                        business.original_tags ->> 'contact:phone',
                        business.original_tags ->> 'phone'
                    ) IS NULL))::int AS missing_phone,
                    (count(*) FILTER (WHERE coalesce(
                        business.original_tags ->> 'contact:website',
                        business.original_tags ->> 'website'
                    ) IS NULL))::int AS missing_website
                FROM businesses AS business
                JOIN business_categories AS category
                  ON category.id = business.category_id
                WHERE business.data_release_id = :release_id
                  AND category.slug = :category_slug
                  AND ST_DWithin(
                      business.geom::geography,
                      ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                      :radius_m
                  )
                """
            ),
            parameters,
        ).mappings().one()
        breakdown: dict[str, dict[str, int]] = {
            "commercial": {},
            "office": {},
            "education": {},
            "healthcare": {},
        }
        for row in poi_rows:
            breakdown[row["evidence_group"]][row["poi_type"]] = row["record_count"]
        return LocationEvidence(
            competitor_subtype_counts=dict(subtype_rows),
            nearest_competitors=[NearbyBusiness(**row) for row in competitors],
            nearest_transport=(
                NearbyTransport(**nearest_transport_row)
                if nearest_transport_row is not None
                else None
            ),
            nearest_major_road=(
                NearbyRoad(**nearest_road_row) if nearest_road_row is not None else None
            ),
            poi_breakdown=PoiBreakdown(**breakdown),
            coverage=AnalysisCoverage(
                total_businesses=coverage_row["total_businesses"],
                named_business_percent=coverage_row["named_business_percent"],
                missing_source_fields={
                    "brand": coverage_row["missing_brand"],
                    "operator": coverage_row["missing_operator"],
                    "opening_hours": coverage_row["missing_opening_hours"],
                    "phone": coverage_row["missing_phone"],
                    "website": coverage_row["missing_website"],
                },
            ),
        )

    def _nearby_optional_count(
        self,
        table_name: str,
        parameters: dict[str, object],
        *,
        poi_types: tuple[str, ...] | None = None,
        distinct_station: bool = False,
    ) -> int | None:
        total = self.session.scalar(
            text(
                f"SELECT count(*) FROM {table_name} "
                "WHERE data_release_id = :release_id"
            ),
            parameters,
        )
        if not total:
            return None
        if table_name == "transport_stops":
            count_expression = (
                "count(DISTINCT coalesce(parent_stop_id, id))"
                if distinct_station
                else "count(*)"
            )
            query = f"""
                SELECT {count_expression}
                FROM transport_stops
                WHERE data_release_id = :release_id
                  AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                    :radius_m
                )
            """
            return int(self.session.scalar(text(query), parameters) or 0)

        poi_parameters = dict(parameters)
        poi_parameters["poi_types"] = list(poi_types or ())
        return int(
            self.session.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM pois
                    WHERE data_release_id = :release_id
                      AND poi_type = ANY(:poi_types)
                      AND ST_DWithin(
                          geom::geography,
                          ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                          :radius_m
                      )
                    """
                ),
                poi_parameters,
            )
            or 0
        )

    def _nearest_road_distance(self, parameters: dict[str, object]) -> float | None:
        if not self.session.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM roads "
                "WHERE data_release_id = :release_id)"
            ),
            parameters,
        ):
            return None
        distance = self.session.scalar(
            text(
                """
                SELECT min(ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography
                ))
                FROM roads
                WHERE data_release_id = :release_id
                  AND road_type IN ('motorway', 'trunk', 'primary', 'secondary')
                """
            ),
            parameters,
        )
        return float(distance) if distance is not None else None
