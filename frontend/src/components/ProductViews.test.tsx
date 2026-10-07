import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalyticsView } from "./AnalyticsView";
import { DemographicsView } from "./DemographicsView";
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
      if (url.includes("/demographics")) {
        return Response.json({
          release_id: 2,
          release_key: "release-20261004",
          dataset_fingerprint: "real-data-fingerprint",
          source_name: "satudata-dki-population-2025",
          source_url: "https://satudata.jakarta.go.id/open-data/detail",
          observed_at: "2025-12-31",
          total_areas: 1,
          covered_areas: 1,
          total_population: 100,
          male: 51,
          female: 49,
          age_gender: [{ age: "00-04", male: 51, female: 49, total: 100 }],
          areas: [{ id: 1, name: "DURI PULO", wilayah: "JAKARTA PUSAT", kecamatan: "GAMBIR", population: 100, population_density: 10000, male: 51, female: 49 }],
        });
      }
      if (url.includes("/layers/population")) {
        return Response.json({ features: [{ id: 1, type: "Feature", properties: { name: "DURI PULO" }, geometry: { type: "Polygon", coordinates: [[[106.8, -6.2], [106.81, -6.2], [106.81, -6.21], [106.8, -6.2]]] } }] });
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

  it("does not restore results from a request after search is cleared", async () => {
    let resolveSearch!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => {
      resolveSearch = resolve;
    })));
    render(<SearchBox onSelect={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(/Search Senayan/), { target: { value: "Senayan" } });
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    await act(async () => {
      resolveSearch(Response.json([{
        id: "area:1", name: "Senayan", result_type: "area", subtitle: "Kelurahan",
        longitude: 106.802, latitude: -6.226, source_record_id: null,
      }]));
    });
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

  it("renders only official resident demographics and its source", async () => {
    render(<DemographicsView releaseId={2} />);
    expect(await screen.findByText("DURI PULO: 100 penduduk; 10.000 jiwa/km²")).toBeInTheDocument();
    expect(screen.getByText("51")).toBeVisible();
    expect(screen.getByText("49")).toBeVisible();
    expect(screen.getByText(/Satu Data Jakarta \/ Dukcapil DKI/)).toBeVisible();
    expect(screen.queryByText(/returning visitors/i)).not.toBeInTheDocument();
    expect(screen.getByText(/gunakan daftar Kelurahan dengan keyboard/)).toBeVisible();
    expect(document.querySelector(".demographics-map")).toHaveAttribute("aria-hidden", "true");
    fireEvent.change(screen.getByLabelText("Kelurahan"), { target: { value: "1" } });
    expect(screen.getByText("100 penduduk")).toBeVisible();
  });
});
