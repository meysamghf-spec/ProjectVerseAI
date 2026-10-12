import type { SceneParams, Task } from "./types";

export interface SceneInstance {
  position: [number, number, number];
  size: [number, number, number];
}

export interface SceneGroup {
  id: string;
  name: string;
  kind: string;
  phase: string;
  color: string;
  taskId?: string;
  appearAt: number;
  instances: SceneInstance[];
  metadata: Record<string, string | number>;
}

export interface SceneModel {
  metaphor: string;
  label: string;
  disclaimer: string;
  groups: SceneGroup[];
  unavailableReason?: string;
}

const PHASE_COLORS: Record<string, string> = {
  preconstruction: "#8ea0b5",
  substructure: "#8d6a4a",
  foundation: "#6b5344",
  basement: "#6e6256",
  superstructure: "#d4a15a",
  envelope: "#7fa7c9",
  mep: "#b07cc6",
  interiors: "#7eae9a",
  closeout: "#c9857a",
  discovery: "#8ea0b5",
  architecture: "#7fa7c9",
  build: "#d4a15a",
  integration: "#7eae9a",
  verification: "#b07cc6",
  release: "#c9857a",
  reference: "#314155",
};

function colorFor(phase: string): string {
  return PHASE_COLORS[phase] || "#8ea0b5";
}

function taskCode(tasks: Task[], phase: string): string | undefined {
  return tasks.find((task) => !task.is_summary && task.phase === phase)?.code;
}

function gridCoords(span: number, spacing: number): number[] {
  const count = Math.max(2, Math.min(8, Math.floor(span / spacing) + 1));
  const step = span / (count - 1);
  const start = -span / 2;
  return Array.from({ length: count }, (_, index) => start + index * step);
}

function construction(scene: SceneParams, tasks: Task[]): SceneModel {
  const floors = scene.floors ?? 0;
  const width = scene.width_m ?? 0;
  const length = scene.length_m ?? 0;
  if (!floors || !width || !length) {
    return {
      metaphor: "procedural-building",
      label: "Conceptual construction massing",
      disclaimer: scene.disclaimer || "Scene parameters are incomplete.",
      groups: [],
      unavailableReason: "Building dimensions are missing. Update the project inputs or regenerate the plan.",
    };
  }
  const basements = scene.basements ?? 0;
  const floorHeight = scene.floor_height_m ?? 3.2;
  const basementHeight = scene.basement_height_m ?? 3.0;
  const coreWidth = scene.core_width_m ?? Math.min(width * 0.22, width * 0.45);
  const coreLength = scene.core_length_m ?? Math.min(length * 0.28, length * 0.45);
  const spacing = scene.column_spacing_m ?? 8;
  const groups: SceneGroup[] = [];
  const rules = scene.rules?.join(" ") || "Procedural massing tied to project phases.";

  groups.push({
    id: "reference-ground",
    name: "Ground reference",
    kind: "reference",
    phase: "reference",
    color: "#1c2836",
    appearAt: 0,
    instances: [{ position: [0, -0.05, 0], size: [width + 16, 0.08, length + 16] }],
    metadata: { rule: "Reference plane only. Not a surveyed site.", width_m: width, length_m: length },
  });

  groups.push({
    id: "foundation",
    name: "Foundation",
    kind: "foundation",
    phase: "substructure",
    color: colorFor("foundation"),
    taskId: taskCode(tasks, "substructure"),
    appearAt: 0.08,
    instances: [
      {
        position: [0, -(basements * basementHeight) - 0.45, 0],
        size: [width + 1.5, 0.7, length + 1.5],
      },
    ],
    metadata: { rule: rules, phase: "substructure" },
  });

  for (let level = 0; level < basements; level += 1) {
    const y = -((level + 0.5) * basementHeight);
    groups.push({
      id: `basement-${level + 1}`,
      name: `Basement ${level + 1}`,
      kind: "basement",
      phase: "substructure",
      color: colorFor("basement"),
      taskId: taskCode(tasks, "substructure"),
      appearAt: 0.12 + ((level + 1) / Math.max(basements, 1)) * 0.12,
      instances: [{ position: [0, y, 0], size: [width, 0.28, length] }],
      metadata: { level: level + 1, height_m: basementHeight, phase: "substructure" },
    });
  }

  const xs = gridCoords(width, spacing);
  const zs = gridCoords(length, spacing);
  for (let floor = 0; floor < floors; floor += 1) {
    const slabY = floor * floorHeight;
    const appearAt = 0.28 + ((floor + 1) / floors) * 0.42;
    groups.push({
      id: `floor-${floor + 1}`,
      name: `Level ${floor + 1} slab`,
      kind: "slab",
      phase: "superstructure",
      color: colorFor("superstructure"),
      taskId: taskCode(tasks, "superstructure"),
      appearAt,
      instances: [{ position: [0, slabY, 0], size: [width, 0.28, length] }],
      metadata: { level: floor + 1, elevation_m: slabY, phase: "superstructure" },
    });
    const columns: SceneInstance[] = [];
    for (const x of xs) {
      for (const z of zs) {
        const insideCore = Math.abs(x) < coreWidth / 2 && Math.abs(z) < coreLength / 2;
        if (insideCore) {
          continue;
        }
        columns.push({
          position: [x, slabY + floorHeight / 2, z],
          size: [0.42, floorHeight, 0.42],
        });
      }
    }
    groups.push({
      id: `columns-${floor + 1}`,
      name: `Level ${floor + 1} columns`,
      kind: "column",
      phase: "superstructure",
      color: "#b8884a",
      taskId: taskCode(tasks, "superstructure"),
      appearAt,
      instances: columns,
      metadata: { level: floor + 1, column_count: columns.length, spacing_m: spacing },
    });
    groups.push({
      id: `envelope-${floor + 1}`,
      name: `Level ${floor + 1} envelope`,
      kind: "envelope",
      phase: "envelope",
      color: colorFor("envelope"),
      taskId: taskCode(tasks, "envelope"),
      appearAt: Math.min(0.96, appearAt + 0.18),
      instances: [{ position: [0, slabY + floorHeight / 2, 0], size: [width + 0.4, floorHeight * 0.92, length + 0.4] }],
      metadata: { level: floor + 1, phase: "envelope", rule: "Envelope volume is a shell placeholder, not a facade design." },
    });
  }

  groups.push({
    id: "core",
    name: "Building core",
    kind: "core",
    phase: "superstructure",
    color: "#5c6b7a",
    taskId: taskCode(tasks, "superstructure"),
    appearAt: 0.34,
    instances: [{ position: [0, (floors * floorHeight) / 2, 0], size: [coreWidth, floors * floorHeight, coreLength] }],
    metadata: { core_width_m: coreWidth, core_length_m: coreLength, rule: "Core size is a visualization assumption." },
  });

  groups.push({
    id: "crane",
    name: "Tower crane",
    kind: "equipment",
    phase: "superstructure",
    color: "#d7dde5",
    taskId: taskCode(tasks, "superstructure"),
    appearAt: 0.3,
    instances: [
      { position: [width / 2 + 2, (floors * floorHeight) / 2, -length / 2 - 2], size: [0.5, floors * floorHeight + 6, 0.5] },
      { position: [width / 4, floors * floorHeight + 3, -length / 2 - 2], size: [width * 0.7, 0.35, 0.35] },
    ],
    metadata: { rule: "The crane marks the structural phase. It is not a rigging study." },
  });

  return {
    metaphor: "procedural-building",
    label: scene.label || "Conceptual construction massing",
    disclaimer:
      scene.disclaimer ||
      "Procedural massing for planning review. It is not an architectural, structural, or code-compliant building model.",
    groups,
  };
}

function diagram(category: string, scene: SceneParams, tasks: Task[]): SceneModel {
  const metaphors: Record<string, string> = {
    software: "system-modules",
    manufacturing: "production-line",
    infrastructure: "linear-alignment",
    urban: "district-blocks",
    logistics: "distribution-network",
    research: "research-layers",
    event: "venue-zones",
    custom: "phase-blocks",
  };
  const leaves = tasks.filter((task) => !task.is_summary);
    const source = leaves.length
      ? leaves
      : (scene.phases || ["define", "build", "integrate"]).map(
          (phase) =>
            ({
              id: phase,
              code: phase,
              name: phase,
              phase,
              is_summary: false,
              is_milestone: false,
              duration: 1,
            }) as Task,
        );
  const groups: SceneGroup[] = source.map((task, index) => {
    const column = index % 4;
    const row = Math.floor(index / 4);
    const y = category === "research" ? index * 2.2 : row * 3;
    const x = category === "research" ? 0 : column * 4.2 - 6;
    const z = category === "logistics" || category === "infrastructure" ? index * 3.4 : row * 0.4;
    return {
      id: `node-${task.code}`,
      name: task.name,
      kind: category === "manufacturing" ? "station" : category === "logistics" ? "node" : "phase",
      phase: task.phase || "custom",
      color: colorFor(task.phase || "build"),
      taskId: task.code,
      appearAt: source.length <= 1 ? 0 : index / (source.length - 1),
      instances: [{ position: [x, y + 1, z], size: [2.4, 1.4, 2.4] }],
      metadata: {
        task: task.code,
        phase: task.phase || "custom",
        rule: "Object position encodes plan sequence, not a measured coordinate.",
      },
    };
  });
  if (category === "logistics" && groups.length > 1) {
    for (let index = 0; index < groups.length - 1; index += 1) {
      const from = groups[index].instances[0].position;
      const to = groups[index + 1].instances[0].position;
      groups.push({
        id: `route-${index + 1}`,
        name: `Route ${index + 1}`,
        kind: "route",
        phase: "lane",
        color: "#7fa7c9",
        appearAt: groups[index + 1].appearAt,
        instances: [
          {
            position: [(from[0] + to[0]) / 2, 0.2, (from[2] + to[2]) / 2],
            size: [0.35, 0.12, Math.max(Math.abs(to[2] - from[2]) - 1.2, 0.8)],
          },
        ],
        metadata: { rule: "Route marker between distribution nodes. Not a surveyed path." },
      });
    }
  }
  return {
    metaphor: scene.metaphor || metaphors[category] || "phase-blocks",
    label: scene.label || `Conceptual ${category.replace(/_/g, " ")} diagram`,
    disclaimer:
      scene.disclaimer ||
      "This is a labeled conceptual diagram of plan entities. It is not a measured site, system architecture, or engineering drawing.",
    groups,
  };
}

export function buildScene(category: string, scene: SceneParams | null | undefined, tasks: Task[] = []): SceneModel {
  const params = scene || {};
  if ((category === "construction" || params.metaphor === "procedural-building") && params.metaphor !== "phase-blocks") {
    if (category === "construction" || params.metaphor === "procedural-building") {
      return construction(params, tasks);
    }
  }
  return diagram(category || "custom", params, tasks);
}
