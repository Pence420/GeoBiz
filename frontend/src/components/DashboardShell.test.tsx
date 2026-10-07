import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DashboardShell } from "./DashboardShell";

afterEach(cleanup);

describe("DashboardShell", () => {
  it("keeps all four deep links and identifies the active view", () => {
    render(<DashboardShell activeView="demographics" releaseKey="release-test"><main id="main-content">Content</main></DashboardShell>);

    expect(screen.getByRole("link", { name: "Map Explorer" })).toHaveAttribute("href", "#overview");
    expect(screen.getByRole("link", { name: "Analytics" })).toHaveAttribute("href", "#analytics");
    expect(screen.getByRole("link", { name: "Demographics" })).toHaveAttribute("href", "#demographics");
    expect(screen.getByRole("link", { name: "Methodology" })).toHaveAttribute("href", "#methodology-view");
    expect(screen.getByRole("link", { name: "Demographics" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByText("DKI Jakarta")).toBeVisible();
    expect(screen.getByText("release-test")).toBeVisible();
  });
});
