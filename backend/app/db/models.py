from datetime import date, datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BusinessCategory(TimestampMixin, Base):
    __tablename__ = "business_categories"
    __table_args__ = (
        CheckConstraint(
            "slug IN ('restaurant', 'gym', 'pharmacy')",
            name="ck_business_categories_supported_slug",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)


class DatasetSource(TimestampMixin, Base):
    __tablename__ = "dataset_sources"
    __table_args__ = (UniqueConstraint("slug", name="uq_dataset_sources_slug"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    license_name: Mapped[str] = mapped_column(Text, nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)


class ImportRun(TimestampMixin, Base):
    __tablename__ = "import_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'validated', 'promoted', 'rejected')",
            name="ck_import_runs_status",
        ),
        Index("ix_import_runs_dataset_source_id", "dataset_source_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_source_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    quality_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdministrativeArea(TimestampMixin, Base):
    __tablename__ = "administrative_areas"
    __table_args__ = (
        UniqueConstraint(
            "dataset_source_id", "source_record_id",
            name="uq_administrative_areas_source_record",
        ),
        Index("ix_administrative_areas_dataset_source_id", "dataset_source_id"),
        Index("ix_administrative_areas_geom_gist", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_source_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    official_code: Mapped[str | None] = mapped_column(Text, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    area_type: Mapped[str] = mapped_column(Text, nullable=False)
    population: Mapped[int | None] = mapped_column(BigInteger)
    population_density: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    observed_at: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False
    )


class Business(TimestampMixin, Base):
    __tablename__ = "businesses"
    __table_args__ = (
        UniqueConstraint(
            "dataset_source_id", "source_type", "source_record_id",
            name="uq_businesses_source_record",
        ),
        Index("ix_businesses_category_id", "category_id"),
        Index("ix_businesses_dataset_source_id", "dataset_source_id"),
        Index("ix_businesses_category_geom", "category_id", "geom", postgresql_using="gist"),
        Index("ix_businesses_geom_gist", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("business_categories.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_source_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_sources.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_observed_at: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )


class Poi(TimestampMixin, Base):
    __tablename__ = "pois"
    __table_args__ = (
        UniqueConstraint(
            "dataset_source_id", "source_type", "source_record_id",
            name="uq_pois_source_record",
        ),
        Index("ix_pois_dataset_source_id", "dataset_source_id"),
        Index("ix_pois_type_geom", "poi_type", "geom", postgresql_using="gist"),
        Index("ix_pois_geom_gist", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_source_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_sources.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text)
    poi_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False
    )


class TransportStop(TimestampMixin, Base):
    __tablename__ = "transport_stops"
    __table_args__ = (
        UniqueConstraint(
            "dataset_source_id", "source_record_id",
            name="uq_transport_stops_source_record",
        ),
        Index("ix_transport_stops_dataset_source_id", "dataset_source_id"),
        Index("ix_transport_stops_parent_stop_id", "parent_stop_id"),
        Index("ix_transport_stops_geom_gist", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_source_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_sources.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    transport_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    parent_stop_id: Mapped[int | None] = mapped_column(
        ForeignKey("transport_stops.id", ondelete="SET NULL")
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )


class Road(TimestampMixin, Base):
    __tablename__ = "roads"
    __table_args__ = (
        UniqueConstraint(
            "dataset_source_id", "source_type", "source_record_id",
            name="uq_roads_source_record",
        ),
        Index("ix_roads_dataset_source_id", "dataset_source_id"),
        Index("ix_roads_type_geom", "road_type", "geom", postgresql_using="gist"),
        Index("ix_roads_geom_gist", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_source_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_sources.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text)
    road_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("MULTILINESTRING", srid=4326, spatial_index=False), nullable=False
    )


class ScoringWeight(TimestampMixin, Base):
    __tablename__ = "scoring_weights"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "version", "factor_name",
            name="uq_scoring_weights_category_version_factor",
        ),
        CheckConstraint("weight >= 0 AND weight <= 1", name="ck_scoring_weights_range"),
        Index("ix_scoring_weights_category_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("business_categories.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    factor_name: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)


class NormalizationProfile(TimestampMixin, Base):
    __tablename__ = "normalization_profiles"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "radius_m", "dataset_fingerprint", "version",
            name="uq_normalization_profiles_scope",
        ),
        CheckConstraint(
            "radius_m IN (500, 1000, 2000, 3000, 5000)",
            name="ck_normalization_profiles_radius",
        ),
        Index("ix_normalization_profiles_category_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("business_categories.id", ondelete="CASCADE"), nullable=False
    )
    radius_m: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    percentiles: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sample_count: Mapped[int] = mapped_column(BigInteger, nullable=False)

