from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.contracts import ContainingArea, NearbyMetrics
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
