import { describe, expect, it } from "vitest";

import { localStyle } from "./localStyle";

describe("localStyle", () => {
  it("contains no external network resources", () => {
    const style = localStyle({
      release_id: 2,
      release_key: "v2-active",
      taxonomy_version: "v2.0.0",
      tile_url: "/tiles/releases/v2-active.pmtiles",
      tile_sha256: "a".repeat(64),
      bounds: [106.45, -6.38, 106.98, -5.6],
      min_zoom: 7,
      max_zoom: 15,
      attribution: "© OpenStreetMap contributors",
      mode: "offline",
      fallback_available: true,
    });

    expect(JSON.stringify(style)).not.toMatch(/https?:\/\//);
    expect(JSON.stringify(style)).toContain("pmtiles:///tiles/releases/v2-active.pmtiles");
  });
});
