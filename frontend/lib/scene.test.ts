import { describe, expect, it } from "vitest";

import { buildScene, elementState, phaseSummary } from "./scene";
import type { SceneParams, Task } from "./types";

function building(floors: number, floorHeight = 3.2): SceneParams {
  const footprint = 25000 / floors;
  const aspect = 1.5;
  const width = Math.sqrt(footprint / aspect);
  return {
    metaphor: "procedural-building",
    floors,
    basements: 3,
    width_m: width,
    length_m: width * aspect,
    floor_height_m: floorHeight,
    basement_height_m: 3,
    core_width_m: 8,
    core_length_m: 10,
    column_spacing_m: 8,
  };
}

const tasks = [
  { code: "CON-SUPER", name: "Superstructure", phase: "superstructure", is_summary: false },
  { code: "CON-ENV", name: "Envelope", phase: "envelope", is_summary: false },
] as Task[];

describe("buildScene", () => {
  it("creates one above-grade slab group per floor and updates when floors change", () => {
    const twenty = buildScene("construction", building(20), tasks);
    const five = buildScene("construction", building(5), tasks);
    const slabs = (floors: number) =>
      buildScene("construction", building(floors), tasks).groups.filter((group) => group.kind === "slab");
    expect(slabs(20)).toHaveLength(20);
    expect(slabs(5)).toHaveLength(5);
    expect(twenty.groups.find((group) => group.id === "core")?.instances[0].size[1]).toBeGreaterThan(
      five.groups.find((group) => group.id === "core")?.instances[0].size[1] || 0,
    );
    expect(twenty.groups.find((group) => group.id === "floor-1")?.taskId).toBe("CON-SUPER");
    expect(twenty.disclaimer.toLowerCase()).toContain("not an architectural");
  });

  it("moves slabs when the floor-to-floor height changes", () => {
    const low = buildScene("construction", building(8, 3), tasks);
    const high = buildScene("construction", building(8, 4), tasks);
    expect(low.groups.find((group) => group.id === "floor-3")?.instances[0].position[1]).toBe(6);
    expect(high.groups.find((group) => group.id === "floor-3")?.instances[0].position[1]).toBe(8);
  });

  it("uses a labeled conceptual diagram for software projects", () => {
    const scene = buildScene(
      "software",
      { metaphor: "system-modules", phases: ["discovery", "build"], disclaimer: "Conceptual diagram." },
      [],
    );
    expect(scene.metaphor).toBe("system-modules");
    expect(scene.groups.some((group) => group.kind === "slab")).toBe(false);
    expect(scene.disclaimer.toLowerCase()).toContain("conceptual");
  });

  it("ties construction geometry to scheduled task windows", () => {
    const scheduled = [
      { code: "CON-SUPER", name: "Superstructure", phase: "superstructure", is_summary: false, start_offset: 100, finish_offset: 300 },
      { code: "CON-ENV", name: "Envelope", phase: "envelope", is_summary: false, start_offset: 300, finish_offset: 420 },
    ] as Task[];
    const scene = buildScene("construction", building(4), scheduled);
    const first = scene.groups.find((group) => group.id === "floor-1");
    const last = scene.groups.find((group) => group.id === "floor-4");
    const envelope = scene.groups.find((group) => group.id === "envelope-1");
    expect(first?.startDay).toBe(100);
    expect(first?.finishDay).toBe(150);
    expect(last?.startDay).toBe(250);
    expect(envelope?.startDay).toBe(300);
    expect(elementState(first!, 0, 420)).toBe("pending");
    expect(elementState(first!, 110, 420)).toBe("active");
    expect(elementState(first!, 160, 420)).toBe("completed");
    expect(phaseSummary(scene.groups, 110, 420).find((item) => item.phase === "superstructure")?.state).toBe("active");
    expect(phaseSummary(scene.groups, 0, 420).find((item) => item.phase === "envelope")?.state).toBe("pending");
  });

  it("reports an honest unavailable state when building dimensions are missing", () => {
    const scene = buildScene("construction", { metaphor: "procedural-building", floors: 4 }, []);
    expect(scene.groups).toHaveLength(0);
    expect(scene.unavailableReason).toBeTruthy();
  });
});
