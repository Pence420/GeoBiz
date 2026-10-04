import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { NearbyEvidence } from "./NearbyEvidence";

afterEach(cleanup);

describe("NearbyEvidence", () => {
  it("renders subtype and nearest-place evidence without inventing missing tags", () => {
    render(<NearbyEvidence analysis={{
      competitor_subtype_counts: { cafe: 3, bakery: 1 },
      nearest_competitors: [{
        name: "Kopi Nyata",
        business_subtype: "cafe",
        distance_m: 275,
        latitude: -6.2,
        longitude: 106.8,
        source_type: "node",
        source_record_id: "123",
        address: null,
        brand: null,
        operator: null,
        opening_hours: null,
        phone: null,
        website: null,
      }],
      nearest_transport: {
        name: "Halte Gambir",
        transport_type: "bus_stop",
        distance_m: 620,
        latitude: -6.18,
        longitude: 106.83,
        source_record_id: "stop-1",
      },
      nearest_major_road: {
        name: "Jalan Merdeka",
        road_type: "primary",
        distance_m: 1250,
        source_type: "way",
        source_record_id: "456",
      },
      coverage: {
        total_businesses: 4,
        named_business_percent: 75,
        missing_source_fields: { phone: 4 },
      },
      containing_area: {
        id: 1,
        name: "Gambir",
        official_code: "3171011001",
        coverage_official_code: "3171011001",
        population_density: 12000,
        area_type: "kelurahan",
        kecamatan: "Gambir",
        population: 25000,
        population_observed_at: "2025-12-31",
      },
    }} />);

    expect(screen.getByText("cafe")).toBeVisible();
    expect(screen.getByText("Kopi Nyata")).toBeVisible();
    expect(screen.getByText(/275 m/)).toBeVisible();
    expect(screen.getByText("1.3 km")).toBeVisible();
    expect(screen.getAllByText("Not mapped").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Gambir").length).toBe(2);
    expect(screen.getByText(/2025/)).toBeVisible();
  });
});
