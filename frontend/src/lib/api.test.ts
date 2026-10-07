import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBusinesses } from "./api";

const page = (start: number, count: number) => ({
  type: "FeatureCollection",
  features: Array.from({ length: count }, (_, index) => ({
    type: "Feature",
    id: start + index,
    geometry: { type: "Point", coordinates: [106.8, -6.2] },
    properties: { name: `Business ${start + index}`, category: "fnb" },
  })),
});

afterEach(() => vi.unstubAllGlobals());

describe("fetchBusinesses", () => {
  it("loads every page, including an exact page boundary", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const offset = Number(new URL(String(input), "http://localhost").searchParams.get("offset"));
      return Response.json(offset === 0 ? page(1, 1000) : offset === 1000 ? page(1001, 1000) : page(2001, 0));
    });
    vi.stubGlobal("fetch", fetchMock);

    const businesses = await fetchBusinesses("fnb", 2);

    expect(businesses).toHaveLength(2000);
    expect(new Set(businesses.map((business) => business.id)).size).toBe(2000);
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      "/api/businesses?category=fnb&limit=1000&offset=0&expected_release_id=2",
      "/api/businesses?category=fnb&limit=1000&offset=1000&expected_release_id=2",
      "/api/businesses?category=fnb&limit=1000&offset=2000&expected_release_id=2",
    ]);
  });

  it("rejects a repeated page instead of reporting partial data as complete", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(page(1, 1000))));
    await expect(fetchBusinesses("fnb", 2)).rejects.toThrow(/repeated/i);
  });

  it("rejects a release switch between pages", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const offset = Number(new URL(String(input), "http://localhost").searchParams.get("offset"));
      return offset === 0
        ? Response.json(page(1, 1000))
        : Response.json({ detail: { code: "RELEASE_CHANGED", message: "the active data release changed; reload the page" } }, { status: 409 });
    }));
    await expect(fetchBusinesses("fnb", 2)).rejects.toThrow(/release changed/i);
  });
});
