import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { KeysPage } from "./developer/KeysPage";
import { PeoplePage } from "./operator/PeoplePage";

describe("collection count labels", () => {
  it("counts zero keys as zero instead of an unknown total", async () => {
    vi.spyOn(api, "listKeys").mockResolvedValue([]);
    render(<MemoryRouter><KeysPage /></MemoryRouter>);

    expect(await screen.findByText("0 keys")).toBeInTheDocument();
  });

  it("counts zero people as zero instead of an unknown total", async () => {
    vi.spyOn(api, "listPeople").mockResolvedValue([]);
    render(<MemoryRouter><PeoplePage /></MemoryRouter>);

    expect(await screen.findByText("0 people")).toBeInTheDocument();
  });

  it("keeps the placeholder while a collection has not loaded", () => {
    vi.spyOn(api, "listKeys").mockReturnValue(new Promise(() => { /* pending */ }));
    render(<MemoryRouter><KeysPage /></MemoryRouter>);

    expect(screen.getByText("— keys")).toBeInTheDocument();
  });
});
