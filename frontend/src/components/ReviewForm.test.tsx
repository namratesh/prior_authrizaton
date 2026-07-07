import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBadge } from "./ReviewForm";

describe("ConfidenceBadge", () => {
  it("renders nothing when confidence is missing", () => {
    const { container } = render(<ConfidenceBadge confidence={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a rounded percentage", () => {
    render(<ConfidenceBadge confidence={0.873} />);
    expect(screen.getByText("87%")).toBeInTheDocument();
  });

  it("uses the destructive (red) variant below 60%", () => {
    render(<ConfidenceBadge confidence={0.4} />);
    const badge = screen.getByText("40%");
    expect(badge.className).toMatch(/bg-red-50/);
  });

  it("uses the success (teal) variant at or above 85%", () => {
    render(<ConfidenceBadge confidence={0.9} />);
    const badge = screen.getByText("90%");
    expect(badge.className).toMatch(/bg-teal-50/);
  });
});
