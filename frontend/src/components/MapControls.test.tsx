import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MapControls, type LayerState } from "./MapControls";

afterEach(cleanup);

const layers: LayerState = {
  opportunity: true,
  competitors: true,
  heatmap: false,
  population: false,
  transport: false,
  commercial: false,
  education: false,
  office: false,
  roads: false,
};

describe("MapControls", () => {
  it("keeps map layers and opportunity filters available without permanently covering the map", () => {
    const onLayersChange = vi.fn();
    const onMinimumScoreChange = vi.fn();
    const { rerender } = render(
      <MapControls category="fnb" radius={1000} layers={layers} minimumScore={0} maximumCompetition={null} minimumPopulation={0} visibleAreas={267} onSelectLocation={vi.fn()} onCategoryChange={vi.fn()} onRadiusChange={vi.fn()} onLayersChange={onLayersChange} onMinimumScoreChange={onMinimumScoreChange} onMaximumCompetitionChange={vi.fn()} onMinimumPopulationChange={vi.fn()} />,
    );

    expect(screen.getByLabelText("Bisnis")).toHaveValue("fnb");
    expect(screen.getByLabelText("Radius")).toHaveValue("1000");
    const layerPanel = screen.getByText("Layers").closest("details");
    const filterPanel = screen.getByText("Filters").closest("details");
    expect(layerPanel).not.toHaveAttribute("open");
    expect(filterPanel).not.toHaveAttribute("open");

    fireEvent.click(screen.getByText("Layers"));
    expect(layerPanel).toHaveAttribute("open");
    fireEvent.click(within(layerPanel as HTMLElement).getByLabelText("Population"));
    expect(onLayersChange).toHaveBeenCalledWith({ ...layers, population: true });

    rerender(
      <MapControls category="fnb" radius={1000} layers={{ ...layers, population: true }} minimumScore={0} maximumCompetition={null} minimumPopulation={0} visibleAreas={267} onSelectLocation={vi.fn()} onCategoryChange={vi.fn()} onRadiusChange={vi.fn()} onLayersChange={onLayersChange} onMinimumScoreChange={onMinimumScoreChange} onMaximumCompetitionChange={vi.fn()} onMinimumPopulationChange={vi.fn()} />,
    );
    fireEvent.click(screen.getByText("Layers"));
    fireEvent.click(screen.getByText("Layers"));
    expect(within(layerPanel as HTMLElement).getByLabelText("Population")).toBeChecked();

    fireEvent.click(screen.getByText("Filters"));
    fireEvent.change(screen.getByLabelText("Minimum score"), { target: { value: "60" } });
    expect(onMinimumScoreChange).toHaveBeenCalledWith(60);
  });
});
