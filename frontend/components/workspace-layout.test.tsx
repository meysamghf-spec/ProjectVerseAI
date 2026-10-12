import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceFrame } from "./WorkspaceFrame";

describe("WorkspaceFrame", () => {
  it("stacks on small screens and sits side by side from the large breakpoint", () => {
    render(<WorkspaceFrame viewport={<div>Viewport</div>} side={<div>Details</div>} />);
    const frame = screen.getByTestId("workspace-frame");
    expect(frame.className).toContain("flex-col");
    expect(frame.className).toContain("lg:flex-row");
    expect(screen.getByText("Viewport")).toBeTruthy();
    expect(screen.getByText("Details")).toBeTruthy();
  });
});
