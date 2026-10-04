import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalyticsView } from "./AnalyticsView";
import { MethodologyView } from "./MethodologyView";
import { SearchBox } from "./SearchBox";

afterEach(cleanup);

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/search")) {
        return Response.json([{
          id: "area:1",
          name: "Senayan",
          result_type: "area",
          subtitle: "Kelurahan",
          longitude: 106.802,
          latitude: -6.226,
          source_record_id: null,
        }]);
      }
      if (url.includes("/analytics")) {
        return Response.json({
          business_category: "fnb",
          radius_m: 1000,
          release_key: "release-20261004",
          taxonomy_version: "v2.0.0",
          scoring_version: "v2.0.0",
          dataset_fingerprint: "real-data-fingerprint",
          category_counts: [
            { category: "fnb", count: 1826 },
            { category: "retail", count: 53 },
            { category: "services", count: 305 },
          ],
          subtype_counts: [
            { subtype: "restaurant", count: 1000 },
            { subtype: "cafe", count: 600 },
            { subtype: "bakery", count: 226 },
          ],
          top_opportunities: [{ area_id: 1, area_name: "SENAYAN", final_score: 88.2, label: "High" }],
          score_distribution: [{ label: "High", minimum: 81, maximum: 100, area_count: 1 }],
          population_competition: [{ area_name: "SENAYAN", population_density: 12000, competitor_count: 5, final_score: 88.2 }],
          coverage: [{ key: "business", label: "Business records", value: 2184, unit: "records", definition: "Traceable records." }],
        });
      }
      return Response.json({
        coverage: "DKI Jakarta",
        release_key: "release-20261004",
        taxonomy_version: "v2.0.0",
        scoring_version: "v2.0.0",
        dataset_fingerprint: "real-data-fingerprint",
        tile_sha256: "abcdef0123456789".repeat(4),
        supported_radii_m: [500, 1000],
        representative_area_method: "One in-polygon point per kelurahan.",
        normalization: "DKI-wide percentile normalization.",
        factor_definitions: { population_density: "Official residents per square kilometre." },
        categories: [
          { category: "fnb", weights: { population_density: 0.3, competition: 0.2, public_transport: 0.15, commercial_activity: 0.15, office_activity: 0.1, road_accessibility: 0.1 } },
          { category: "retail", weights: { population_density: 0.25, competition: 0.2, public_transport: 0.1, commercial_activity: 0.2, office_activity: 0.1, road_accessibility: 0.15 } },
          { category: "services", weights: { population_density: 0.2, competition: 0.2, public_transport: 0.15, commercial_activity: 0.1, office_activity: 0.2, road_accessibility: 0.15 } },
        ],
        taxonomy_rules: [
          { category: "fnb", subtype: "restaurant", required_tags: { amenity: "restaurant" } },
          { category: "retail", subtype: "supermarket", required_tags: { shop: "supermarket" } },
          { category: "services", subtype: "gym", required_tags: { leisure: "fitness_centre" } },
        ],
        datasets: [{
          slug: "osm-businesses",
          provider: "OpenStreetMap",
          source_url: "https://www.openstreetmap.org",
          license_name: "ODbL",
          attribution: "© OpenStreetMap contributors",
          observed_at: "2026-09-20T00:00:00Z",
          retrieved_at: "2026-09-21T00:00:00Z",
          sha256: "1234567890abcdef".repeat(4),
        }],
        limitations: [
          "Source coverage can be incomplete.",
          "A score is comparative evidence, not predicted revenue.",
        ],
      });
    }),
  );
});

describe("PRD product views", () => {
  it("searches local DKI records and returns coordinates", async () => {
    const onSelect = vi.fn();
    render(<SearchBox onSelect={onSelect} />);
    fireEvent.change(screen.getByPlaceholderText(/Search Senayan/), { target: { value: "Senayan" } });
    fireEvent.click(await screen.findByRole("option", { name: /Senayan/ }));
    expect(onSelect).toHaveBeenCalledWith(106.802, -6.226);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("renders evidence-based analytics without fabricated revenue metrics", async () => {
    render(<AnalyticsView category="fnb" radius={1000} onCategoryChange={vi.fn()} onRadiusChange={vi.fn()} />);
    expect(await screen.findByText("1.826")).toBeVisible();
    expect(screen.getAllByText("SENAYAN").length).toBeGreaterThan(0);
    expect(screen.getByText("restaurant")).toBeVisible();
    expect(screen.getByText(/Release release-20261004/)).toBeVisible();
    expect(screen.getByText(/267 representative/)).toBeVisible();
    expect(screen.getByText(/Retail records/)).toBeVisible();
    expect(screen.getByText(/Services records/)).toBeVisible();
    expect(screen.queryByText(/^Revenue$/i)).not.toBeInTheDocument();
  });

  it("renders scoring provenance and limitations", async () => {
    render(<MethodologyView />);
    expect(await screen.findByText("OpenStreetMap")).toBeVisible();
    expect(screen.getByText("ODbL")).toBeVisible();
    expect(screen.getByText("Source coverage can be incomplete.")).toBeVisible();
    expect(screen.getByText("A score is comparative evidence, not predicted revenue.")).toBeVisible();
    expect(screen.getByText("supermarket")).toBeVisible();
    expect(screen.getByText("30%")).toBeVisible();
    expect(screen.getByText(/abcdef0123456789/)).toBeVisible();
    expect(screen.getByText("release-20261004")).toBeVisible();
    expect(screen.getByText(/real-data-fingerprint/)).toBeVisible();
  });
});
