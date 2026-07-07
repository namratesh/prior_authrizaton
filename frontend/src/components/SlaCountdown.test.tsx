import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SlaCountdown from "./SlaCountdown";

describe("SlaCountdown", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when there is no SLA deadline", () => {
    const { container } = render(<SlaCountdown slaDeadline={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows Overdue once the deadline has passed", () => {
    vi.useFakeTimers().setSystemTime(new Date("2026-01-02T00:00:00Z"));
    render(<SlaCountdown slaDeadline="2026-01-01T00:00:00Z" />);
    expect(screen.getByText("Overdue")).toBeInTheDocument();
  });

  it("shows hours/minutes remaining before the deadline", () => {
    vi.useFakeTimers().setSystemTime(new Date("2026-01-01T00:00:00Z"));
    render(<SlaCountdown slaDeadline="2026-01-01T05:30:00Z" />);
    expect(screen.getByText("5h 30m left")).toBeInTheDocument();
  });

  it("shows days remaining when more than a day out", () => {
    vi.useFakeTimers().setSystemTime(new Date("2026-01-01T00:00:00Z"));
    render(<SlaCountdown slaDeadline="2026-01-03T02:00:00Z" />);
    expect(screen.getByText("2d 2h left")).toBeInTheDocument();
  });
});
