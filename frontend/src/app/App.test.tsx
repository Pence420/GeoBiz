import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("../components/GeoMap", () => ({
  GeoMap: () => <div aria-label="Peta interaktif bisnis DKI Jakarta" />,
}));

afterEach(cleanup);

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/business-categories")) {
        return Response.json([
          { slug: "restaurant", name: "Restaurant", business_count: 1826 },
        ]);
      }
      if (url.includes("/businesses")) {
        return Response.json({ type: "FeatureCollection", features: [] });
      }
      if (url.includes("/opportunity-map")) {
        return Response.json({ type: "FeatureCollection", features: [] });
      }
      if (url.includes("/area-rankings")) {
        return Response.json({
          business_category: "restaurant",
          radius_m: 1000,
          scoring_version: "v1.0.0",
          dataset_fingerprint: "1262b5d3ef6e4ca35d7710f57a6b3298",
          items: ["Area A", "Area B", "Area C", "Area D"].map((name, index) => ({
            area_id: index + 1,
            area_name: name,
            rank: index + 1,
            final_score: 90 - index,
            label: "High",
            longitude: 106.8 + index / 100,
            latitude: -6.2,
            normalized_factors: {
              population_density: 90,
              competition: 80,
              road_accessibility: 70,
            },
            raw_factors: {},
            representative_method: "point_on_surface",
          })),
        });
      }
      return Response.json({
        containing_area: { name: "GAMBIR", population_density: 1093.87 },
        nearby_metrics: {
          competitor_count: 26,
          transport_stop_count: 50,
          commercial_poi_count: 69,
          office_count: 93,
          university_count: 9,
          healthcare_count: 2,
          population_density: 1093.87,
          nearest_major_road_m: 338.5,
        },
        score: {
          status: "complete",
          final_score: 51.2,
          label: "Moderate",
          normalized_factors: { competition: 4.7, office_activity: 100 },
          raw_factors: { competition: 26, office_activity: 93 },
          weights: { competition: 0.2, office_activity: 0.2 },
          missing_factors: [],
          scoring_version: "v1.0.0",
        },
        dataset_fingerprint: "1262b5d3ef6e4ca35d7710f57a6b3298",
        limitations: [],
      });
    }),
  );
});

describe("App", () => {
  it("renders the GeoBiz product name", async () => {
    render(<App />);

    expect(screen.getByLabelText("GeoBiz home")).toBeVisible();
    expect(screen.getByText("Bisnis nyata di DKI Jakarta")).toBeVisible();
    expect(
      await screen.findByLabelText("Peta interaktif bisnis DKI Jakarta"),
    ).toBeVisible();
  });

  it("limits area comparison to three ranked areas", async () => {
    render(<App />);

    const first = await screen.findByLabelText("Compare Area A");
    fireEvent.click(first);
    fireEvent.click(screen.getByLabelText("Compare Area B"));
    fireEvent.click(screen.getByLabelText("Compare Area C"));

    expect(screen.getByLabelText("Compare Area D")).toBeDisabled();
    expect(screen.getByLabelText("Area comparison")).toHaveTextContent("3/3 pinned");
  });

  it("ignores a stale ranking response after radius changes", async () => {
    vi.mocked(fetch).mockImplementation(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/business-categories")) {
        return Response.json([{ slug: "restaurant", business_count: 1826 }]);
      }
      if (url.includes("/businesses")) {
        return Response.json({ type: "FeatureCollection", features: [] });
      }
      if (url.includes("/opportunity-map")) {
        return Response.json({ type: "FeatureCollection", features: [] });
      }
      if (url.includes("/area-rankings")) {
        const stale = url.includes("radius_m=1000");
        if (stale) await new Promise((resolve) => setTimeout(resolve, 60));
        return Response.json({
          business_category: "restaurant",
          radius_m: stale ? 1000 : 2000,
          scoring_version: "v1.0.0",
          dataset_fingerprint: "fingerprint",
          items: [{
            area_id: stale ? 1 : 2,
            area_name: stale ? "STALE AREA" : "CURRENT AREA",
            rank: 1,
            final_score: stale ? 99 : 88,
            label: "High",
            longitude: 106.8,
            latitude: -6.2,
            normalized_factors: {},
            raw_factors: {},
            representative_method: "point_on_surface",
          }],
        });
      }
      return Response.json({
        containing_area: { name: "GAMBIR", population_density: 1000 },
        nearby_metrics: {
          competitor_count: 0,
          transport_stop_count: 0,
          commercial_poi_count: 0,
          office_count: 0,
          university_count: 0,
          healthcare_count: 0,
          population_density: 1000,
          nearest_major_road_m: 0,
        },
        score: {
          status: "complete",
          final_score: 50,
          label: "Moderate",
          normalized_factors: {},
          raw_factors: {},
          weights: {},
          missing_factors: [],
          scoring_version: "v1.0.0",
        },
        dataset_fingerprint: "fingerprint",
        limitations: [],
      });
    });
    render(<App />);

    fireEvent.change(screen.getAllByRole("combobox")[1], {
      target: { value: "2000" },
    });

    expect(await screen.findByText("CURRENT AREA")).toBeVisible();
    await act(() => new Promise((resolve) => setTimeout(resolve, 80)));
    expect(screen.queryByText("STALE AREA")).not.toBeInTheDocument();
  });
});
