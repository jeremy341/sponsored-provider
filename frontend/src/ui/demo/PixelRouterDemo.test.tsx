import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PixelRouterDemo } from "./PixelRouterDemo";

describe("PixelRouterDemo", () => {
  it("starts on the populated overview and switches between showcase pages", () => {
    render(<PixelRouterDemo />);

    expect(screen.getByRole("heading", { name: "AI Router Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("133,482")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Models" }));
    expect(screen.getByRole("heading", { name: "Models" })).toBeInTheDocument();
    expect(screen.getByText("GLM 5.3 Flash")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "API Keys" }));
    expect(screen.getByRole("heading", { name: "API Keys" })).toBeInTheDocument();
    expect(screen.getByText("Web App")).toBeInTheDocument();
  });

  it("labels the showcase as demo data rather than real account telemetry", () => {
    render(<PixelRouterDemo />);

    expect(screen.getByText("Demo data")).toBeInTheDocument();
  });
});
