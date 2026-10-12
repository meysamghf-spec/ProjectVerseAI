"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import { Component, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";

import { buildScene, type SceneGroup, type SceneModel } from "@/lib/scene";
import type { ProjectDetail } from "@/lib/types";

class SceneErrorBoundary extends Component<{ children: ReactNode }, { message: string | null }> {
  state = { message: null as string | null };

  static getDerivedStateFromError(error: Error) {
    return { message: error.message || "The 3D view failed to start." };
  }

  render() {
    if (this.state.message) {
      return (
        <div role="alert" className="grid h-full place-items-center p-6 text-center text-sm text-coral">
          The 3D view could not start. {this.state.message}
        </div>
      );
    }
    return this.props.children;
  }
}

function GroupMesh({
  group,
  selected,
  progress,
  onSelect,
}: {
  group: SceneGroup;
  selected: boolean;
  progress: number;
  onSelect: (id: string) => void;
}) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const built = group.appearAt <= progress + 1e-6;
  useLayoutEffect(() => {
    const mesh = ref.current;
    if (!mesh) {
      return;
    }
    const dummy = new THREE.Object3D();
    group.instances.forEach((instance, index) => {
      dummy.position.set(instance.position[0], instance.position[1], instance.position[2]);
      dummy.scale.set(instance.size[0], instance.size[1], instance.size[2]);
      dummy.updateMatrix();
      mesh.setMatrixAt(index, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
  }, [group]);
  if (group.instances.length === 0) {
    return null;
  }
  const opacity = built ? (group.kind === "envelope" ? 0.22 : 0.94) : 0.08;
  return (
    <instancedMesh
      ref={ref}
      args={[undefined, undefined, group.instances.length]}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(group.id);
      }}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial
        color={selected ? "#f6e2bc" : group.color}
        transparent
        opacity={opacity}
        wireframe={!built && group.kind !== "reference"}
        roughness={0.78}
        metalness={0.05}
      />
    </instancedMesh>
  );
}

function CameraReset({ signal, focus }: { signal: number; focus: [number, number, number] }) {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls) as { target?: THREE.Vector3; update?: () => void } | null;
  useEffect(() => {
    camera.position.set(focus[0], focus[1], focus[2]);
    controls?.target?.set(0, Math.max(focus[1] * 0.25, 4), 0);
    controls?.update?.();
  }, [signal, camera, controls, focus]);
  return null;
}

function SceneStage({
  model,
  progress,
  hidden,
  selected,
  onSelect,
  resetSignal,
}: {
  model: SceneModel;
  progress: number;
  hidden: Set<string>;
  selected: string | null;
  onSelect: (id: string | null) => void;
  resetSignal: number;
}) {
  const grid = useMemo(() => new THREE.GridHelper(90, 30, "#3d4c5c", "#243140"), []);
  const axes = useMemo(() => new THREE.AxesHelper(8), []);
  const focus = useMemo<[number, number, number]>(() => {
    const height = model.groups.find((group) => group.id === "core")?.instances[0]?.size[1] || 24;
    return [height * 0.9, height * 0.72, height * 0.9];
  }, [model]);
  return (
    <Canvas camera={{ position: focus, fov: 42 }} dpr={[1, 1.75]} onPointerMissed={() => onSelect(null)}>
      <color attach="background" args={["#121922"]} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[30, 40, 20]} intensity={1.15} />
      <hemisphereLight args={["#d7e4f2", "#2a2118", 0.35]} />
      <primitive object={grid} />
      <primitive object={axes} />
      <CameraReset signal={resetSignal} focus={focus} />
      <OrbitControls makeDefault enableDamping />
      {model.groups
        .filter((group) => !hidden.has(group.id))
        .map((group) => (
          <GroupMesh
            key={`${group.id}-${group.instances.length}`}
            group={group}
            selected={selected === group.id}
            progress={progress}
            onSelect={onSelect}
          />
        ))}
    </Canvas>
  );
}

export default function ProjectScene({ project }: { project: ProjectDetail }) {
  const model = useMemo(
    () => buildScene(project.category, project.scene, project.tasks),
    [project.category, project.scene, project.tasks],
  );
  const duration = project.latest_simulation?.result?.project_duration || 0;
  const [day, setDay] = useState(duration);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(5);
  const [selected, setSelected] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [resetSignal, setResetSignal] = useState(0);
  const progress = duration > 0 ? Math.min(day / duration, 1) : 1;
  const selectedGroup = model.groups.find((group) => group.id === selected) || null;

  useEffect(() => {
    setDay(duration);
  }, [duration, project.id]);

  useEffect(() => {
    if (!playing) {
      return;
    }
    const timer = window.setInterval(() => {
      setDay((current) => {
        const next = current + speed;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
    }, 180);
    return () => window.clearInterval(timer);
  }, [playing, speed, duration]);

  function toggle(id: string) {
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div className="panel flex h-full min-h-[50vh] flex-col overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
        <div>
          <p className="font-display text-lg">{model.label}</p>
          <p className="text-xs uppercase tracking-[0.14em] text-muted">{model.metaphor}</p>
        </div>
        <button className="btn secondary" type="button" onClick={() => setResetSignal((value) => value + 1)}>
          Reset view
        </button>
      </div>
      <div className="relative min-h-[42vh] flex-1" role="img" aria-label={model.label}>
        {model.unavailableReason ? (
          <div className="grid h-full place-items-center p-6 text-center text-sm text-muted">{model.unavailableReason}</div>
        ) : (
          <SceneErrorBoundary>
            <SceneStage
              model={model}
              progress={progress}
              hidden={hidden}
              selected={selected}
              onSelect={setSelected}
              resetSignal={resetSignal}
            />
          </SceneErrorBoundary>
        )}
      </div>
      <div className="space-y-3 border-t border-line p-4">
        <p className="text-sm text-muted">{model.disclaimer}</p>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn" type="button" onClick={() => setPlaying((value) => !value)} disabled={!duration}>
            {playing ? "Pause" : "Play"}
          </button>
          <button
            className="btn secondary"
            type="button"
            onClick={() => {
              setPlaying(false);
              setDay(0);
            }}
          >
            Restart
          </button>
          <label className="text-sm text-muted">
            Speed
            <select className="field ml-2 w-auto" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
              <option value={1}>1 day/tick</option>
              <option value={5}>5 days/tick</option>
              <option value={15}>15 days/tick</option>
              <option value={30}>30 days/tick</option>
            </select>
          </label>
        </div>
        <label className="block text-sm">
          Simulation day {Math.round(day)} {duration ? `of ${Math.round(duration)}` : ""}
          <input
            className="mt-2 w-full"
            type="range"
            min={0}
            max={duration || 1}
            step={1}
            value={Math.min(day, duration || 1)}
            aria-label="Simulation day"
            onChange={(event) => {
              setPlaying(false);
              setDay(Number(event.target.value));
            }}
          />
        </label>
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="max-h-40 space-y-1 overflow-auto pr-1 text-sm">
            {model.groups.map((group) => (
              <label key={group.id} className="flex items-center gap-2">
                <input type="checkbox" checked={!hidden.has(group.id)} onChange={() => toggle(group.id)} />
                <button type="button" className="truncate text-left hover:text-amber" onClick={() => setSelected(group.id)}>
                  {group.name}
                </button>
              </label>
            ))}
          </div>
          <div className="rounded-xl bg-black/20 p-3 text-sm">
            {selectedGroup ? (
              <>
                <p className="font-medium">{selectedGroup.name}</p>
                <p className="text-muted">
                  {selectedGroup.kind} · {selectedGroup.phase}
                  {selectedGroup.taskId ? ` · task ${selectedGroup.taskId}` : ""}
                </p>
                <dl className="mt-2 space-y-1">
                  {Object.entries(selectedGroup.metadata).map(([key, value]) => (
                    <div key={key} className="flex justify-between gap-3">
                      <dt className="text-muted">{key}</dt>
                      <dd className="text-right">{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </>
            ) : (
              <p className="text-muted">Select an object to see the planning entity or visualization rule behind it.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
