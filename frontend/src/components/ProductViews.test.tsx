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
          scoring_version: "v1.0.0",
          dataset_fingerprint: "real-data-fingerprint",
          category_counts: [
            { category: "fnb", count: 1826 },
            { category: "retail", count: 53 },
            { category: "services", count: 305 },
          ],
          top_opportunities: [{ area_id: 1, area_name: "SENAYAN", final_score: 88.2, label: "High" }],
          score_distribution: [{ label: "High", minimum: 81, maximum: 100, area_count: 1 }],
          population_competition: [{ area_name: "SENAYAN", population_density: 12000, competitor_count: 5, final_score: 88.2 }],
          coverage: [{ key: "business", label: "Business records", value: 2184, unit: "records", definition: "Traceable records." }],
        });
      }
      return Response.json({
        coverage: "DKI Jakarta",
        scoring_version: "v1.0.0",
        dataset_fingerprint: "real-data-fingerprint",
        supported_radii_m: [500, 1000],
        representative_area_method: "One in-polygon point per kelurahan.",
        normalization: "DKI-wide percentile normalization.",
        factor_definitions: { population_density: "Official residents per square kilometre." },
        categories: [
          { category: "fnb", weights: { population_density: 1 } },
          { category: "retail", weights: { population_density: 1 } },
          { category: "services", weights: { population_density: 1 } },
        ],
        datasets: [{
          slug: "osm-businesses",
          provider: "OpenStreetMap",
          source_url: "https://www.openstreetmap.org",
          license_name: "ODbL",
          attribution: "© OpenStreetMap contributors",
          observed_at: "2026-09-20T00:00:00Z",
          retrieved_at: "2026-09-21T00:00:00Z",
        }],
        limitations: ["Source coverage can be incomplete."],
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
    expect(screen.queryByText(/^Revenue$/i)).not.toBeInTheDocument();
  });

  it("renders scoring provenance and limitations", async () => {
    render(<MethodologyView />);
    expect(await screen.findByText("OpenStreetMap")).toBeVisible();
    expect(screen.getByText("ODbL")).toBeVisible();
    expect(screen.getByText("Source coverage can be incomplete.")).toBeVisible();
    expect(screen.getByText(/real-data-fingerprint/)).toBeVisible();
  });
});
