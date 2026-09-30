import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("../components/GeoMap", () => ({
  GeoMap: () => <div aria-label="Peta interaktif bisnis DKI Jakarta" />,
}));

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/categories")) {
        return Response.json([
          { slug: "restaurant", name: "Restaurant", business_count: 1826 },
        ]);
      }
      if (url.includes("/businesses")) {
        return Response.json({ type: "FeatureCollection", features: [] });
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
        score: { status: "complete", final_score: 51.2, label: "Moderate" },
        dataset_fingerprint: "1262b5d3ef6e4ca35d7710f57a6b3298",
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
});
