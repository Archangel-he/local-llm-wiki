import Graph from "graphology";
import {
  ChevronDown,
  ChevronRight,
  CircleDot,
  Eye,
  Filter,
  Focus,
  Maximize2,
  Minimize2,
  Minus,
  Orbit,
  Palette,
  Plus,
  RefreshCcw,
  Search,
  Settings2,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import Sigma from "sigma";
import { EdgeArrowProgram, EdgeLineProgram } from "sigma/rendering";
import { graphEdges, graphNodes } from "../fixtures/workspace";

interface GraphWorkspaceProps {
  selectedPageId: string;
  onSelectPage: (pageId: string) => void;
  maximized: boolean;
  onToggleMaximize: () => void;
}

interface NodeMotion {
  targetX: number;
  targetY: number;
  targetSize: number;
  velocityX: number;
  velocityY: number;
  velocitySize: number;
  delayUntil: number;
}

interface InteractionState {
  hovered: string | null;
  hoverTarget: number;
  hoverAmount: number;
  selected: string | null;
  selectedPulse: number;
  dragging: string | null;
}

const groupColors = {
  source: "#7b6fe3",
  entity: "#5d83c7",
  concept: "#8c6ec7",
  question: "#c17b63",
};

const finalPositions = Object.fromEntries(
  graphNodes.map((node) => [
    node.id,
    { x: node.x, y: node.y, size: node.size },
  ]),
);

function mixColor(from: string, to: string, amount: number) {
  const start = [1, 3, 5].map((index) =>
    Number.parseInt(from.slice(index, index + 2), 16),
  );
  const end = [1, 3, 5].map((index) =>
    Number.parseInt(to.slice(index, index + 2), 16),
  );
  return `#${start
    .map((value, index) =>
      Math.round(value + (end[index] - value) * amount)
        .toString(16)
        .padStart(2, "0"),
    )
    .join("")}`;
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="graph-toggle">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <i aria-hidden="true" />
    </label>
  );
}

function SettingsGroup({
  icon,
  title,
  open,
  onToggle,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="graph-settings-group">
      <button type="button" onClick={onToggle} aria-expanded={open}>
        {open ? <ChevronDown /> : <ChevronRight />}
        {icon}
        <span>{title}</span>
      </button>
      {open && <div className="graph-settings-body">{children}</div>}
    </section>
  );
}

export function GraphWorkspace({
  selectedPageId,
  onSelectPage,
  maximized,
  onToggleMaximize,
}: GraphWorkspaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const rendererRef = useRef<Sigma | null>(null);
  const motionsRef = useRef<Record<string, NodeMotion>>({});
  const frameRef = useRef<number | null>(null);
  const previousTimeRef = useRef(0);
  const interactionRef = useRef<InteractionState>({
    hovered: null,
    hoverTarget: 0,
    hoverAmount: 0,
    selected: null,
    selectedPulse: 0,
    dragging: null,
  });
  const renderControlsRef = useRef({
    nodeScale: 1.15,
    edgeScale: 1.15,
    showOrphans: true,
    localOnly: false,
  });
  const previousSelectionRef = useRef(selectedPageId);
  const ensureAnimationRef = useRef<() => void>(() => undefined);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [openGroups, setOpenGroups] = useState(
    () => new Set(["filters", "display", "forces"]),
  );
  const [showOrphans, setShowOrphans] = useState(true);
  const [showArrows, setShowArrows] = useState(false);
  const [nodeScale, setNodeScale] = useState(1.15);
  const [edgeScale, setEdgeScale] = useState(1.15);
  const [centerForce, setCenterForce] = useState(1);
  const [localOnly, setLocalOnly] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);
  const reducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const toggleGroup = (group: string) => {
    setOpenGroups((current) => {
      const next = new Set(current);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  const replayLayout = useCallback(() => {
    const graph = graphRef.current;
    const renderer = rendererRef.current;
    if (!graph || !renderer) return;

    const now = window.performance.now();
    graphNodes.forEach((node, index) => {
      const target = finalPositions[node.id];
      const currentX = graph.getNodeAttribute(node.id, "x") as number;
      const currentY = graph.getNodeAttribute(node.id, "y") as number;
      graph.mergeNodeAttributes(node.id, {
        x: currentX * 0.18,
        y: currentY * 0.18,
        size: 2.2,
      });
      motionsRef.current[node.id] = {
        targetX: target.x * centerForce,
        targetY: target.y * centerForce,
        targetSize: target.size,
        velocityX: 0,
        velocityY: 0,
        velocitySize: 0,
        delayUntil: reducedMotion ? 0 : now + index * 58,
      };
    });

    const camera = renderer.getCamera();
    if (reducedMotion) {
      camera.animatedReset({ duration: 0 });
    } else {
      camera.setState({ x: 0.5, y: 0.5, ratio: 0.82 });
      camera.animate(
        { x: 0.5, y: 0.5, ratio: 1.16 },
        { duration: 920, easing: "cubicOut" },
      );
    }
    ensureAnimationRef.current();
  }, [centerForce, reducedMotion]);

  useEffect(() => {
    if (!containerRef.current) return;

    const graph = new Graph();
    const now = window.performance.now();
    graphNodes.forEach((node, index) => {
      const startX = reducedMotion ? node.x : node.x * 0.08;
      const startY = reducedMotion ? node.y : node.y * 0.08;
      graph.addNode(node.id, {
        label: node.label,
        pageId: node.pageId,
        x: startX,
        y: startY,
        size: reducedMotion ? node.size : 2.2,
        color: groupColors[node.type],
        baseColor: groupColors[node.type],
        baseSize: node.size,
      });
      motionsRef.current[node.id] = {
        targetX: node.x,
        targetY: node.y,
        targetSize: node.size,
        velocityX: 0,
        velocityY: 0,
        velocitySize: 0,
        delayUntil: reducedMotion ? 0 : now + index * 58,
      };
    });
    graphEdges.forEach((edge) => {
      graph.addDirectedEdgeWithKey(edge.id, edge.source, edge.target, {
        label: edge.type,
        color: "#a8a8ad",
        size: 1.25,
        type: "line",
      });
    });

    const renderer = new Sigma(graph, containerRef.current, {
      allowInvalidContainer: true,
      defaultEdgeColor: "#a8a8ad",
      edgeProgramClasses: {
        arrow: EdgeArrowProgram,
        line: EdgeLineProgram,
      },
      enableEdgeEvents: true,
      hideEdgesOnMove: false,
      labelColor: { color: "#3f3f43" },
      labelDensity: 1,
      labelFont:
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif",
      labelRenderedSizeThreshold: 4,
      labelSize: 12,
      labelWeight: "500",
      renderEdgeLabels: false,
      stagePadding: 70,
      zIndex: true,
    });

    graphRef.current = graph;
    rendererRef.current = renderer;

    renderer.setSetting("nodeReducer", (node, data) => {
      const interaction = interactionRef.current;
      const controls = renderControlsRef.current;
      const orphan = graph.degree(node) === 0;
      const isSelected = node === interaction.selected;
      const isHovered = node === interaction.hovered;
      const connectedToHover =
        interaction.hovered !== null &&
        (node === interaction.hovered ||
          graph.areNeighbors(node, interaction.hovered));
      const connectedToSelection =
        interaction.selected !== null &&
        (node === interaction.selected ||
          graph.areNeighbors(node, interaction.selected));
      const dimmedByHover =
        interaction.hovered !== null && !connectedToHover;
      const hiddenByLocal =
        controls.localOnly &&
        interaction.selected !== null &&
        !connectedToSelection;
      const dim = dimmedByHover ? interaction.hoverAmount * 0.78 : 0;
      return {
        ...data,
        color: mixColor(data.color, "#dddde1", dim),
        forceLabel: true,
        hidden: (!controls.showOrphans && orphan) || hiddenByLocal,
        highlighted: isSelected || interaction.dragging === node,
        label:
          dimmedByHover && interaction.hoverAmount > 0.88
            ? ""
            : data.label,
        size:
          data.size *
          controls.nodeScale *
          (isHovered ? 1 + interaction.hoverAmount * 0.2 : 1) *
          (isSelected ? 1 + interaction.selectedPulse * 0.08 : 1),
        zIndex: isHovered || isSelected ? 3 : connectedToHover ? 2 : 1,
      };
    });
    renderer.setSetting("edgeReducer", (edge, data) => {
      const interaction = interactionRef.current;
      const controls = renderControlsRef.current;
      const touchesHover =
        interaction.hovered !== null &&
        (graph.source(edge) === interaction.hovered ||
          graph.target(edge) === interaction.hovered);
      const touchesSelection =
        interaction.selected !== null &&
        (graph.source(edge) === interaction.selected ||
          graph.target(edge) === interaction.selected);
      const hiddenByLocal = controls.localOnly && !touchesSelection;
      return {
        ...data,
        color:
          interaction.hovered && !touchesHover
            ? mixColor("#a8a8ad", "#e5e5e8", interaction.hoverAmount)
            : touchesHover
              ? "#7469d8"
              : "#a8a8ad",
        hidden: hiddenByLocal,
        size:
          data.size *
          controls.edgeScale *
          (touchesHover ? 1 + interaction.hoverAmount * 0.8 : 1),
        zIndex: touchesHover ? 2 : 1,
      };
    });
    const refreshReducers = () => renderer.refresh();

    const tick = (time: number) => {
      frameRef.current = null;
      const delta = Math.min(
        1.9,
        Math.max(0.35, (time - (previousTimeRef.current || time)) / 16.667),
      );
      previousTimeRef.current = time;
      let active = false;

      graph.forEachNode((node) => {
        const motion = motionsRef.current[node];
        if (!motion || time < motion.delayUntil) {
          if (motion && time < motion.delayUntil) active = true;
          return;
        }

        const x = graph.getNodeAttribute(node, "x") as number;
        const y = graph.getNodeAttribute(node, "y") as number;
        const size = graph.getNodeAttribute(node, "size") as number;
        const isDragged = interactionRef.current.dragging === node;
        const stiffness = isDragged ? 0.22 : 0.105;
        const damping = Math.pow(isDragged ? 0.62 : 0.72, delta);

        motion.velocityX =
          (motion.velocityX + (motion.targetX - x) * stiffness * delta) *
          damping;
        motion.velocityY =
          (motion.velocityY + (motion.targetY - y) * stiffness * delta) *
          damping;
        motion.velocitySize =
          (motion.velocitySize +
            (motion.targetSize - size) * 0.14 * delta) *
          Math.pow(0.68, delta);

        const nextX = x + motion.velocityX * delta;
        const nextY = y + motion.velocityY * delta;
        const nextSize = size + motion.velocitySize * delta;
        graph.mergeNodeAttributes(node, {
          x: nextX,
          y: nextY,
          size: nextSize,
        });

        const unsettled =
          Math.abs(motion.targetX - nextX) > 0.00035 ||
          Math.abs(motion.targetY - nextY) > 0.00035 ||
          Math.abs(motion.targetSize - nextSize) > 0.006 ||
          Math.abs(motion.velocityX) > 0.0002 ||
          Math.abs(motion.velocityY) > 0.0002;
        if (unsettled || isDragged) active = true;
      });

      const interaction = interactionRef.current;
      const hoverDelta = interaction.hoverTarget - interaction.hoverAmount;
      if (Math.abs(hoverDelta) > 0.002) {
        interaction.hoverAmount +=
          hoverDelta * (interaction.hoverTarget ? 0.19 : 0.135) * delta;
        active = true;
      } else {
        interaction.hoverAmount = interaction.hoverTarget;
        if (interaction.hoverAmount === 0) interaction.hovered = null;
      }

      if (interaction.selectedPulse > 0.002) {
        interaction.selectedPulse *= Math.pow(0.88, delta);
        active = true;
      } else {
        interaction.selectedPulse = 0;
      }

      refreshReducers();
      if (active) frameRef.current = window.requestAnimationFrame(tick);
    };

    const ensureAnimation = () => {
      if (reducedMotion) {
        graph.forEachNode((node) => {
          const motion = motionsRef.current[node];
          if (!motion) return;
          graph.mergeNodeAttributes(node, {
            x: motion.targetX,
            y: motion.targetY,
            size: motion.targetSize,
          });
        });
        interactionRef.current.hoverAmount =
          interactionRef.current.hoverTarget;
        refreshReducers();
        return;
      }
      if (frameRef.current === null) {
        previousTimeRef.current = window.performance.now();
        frameRef.current = window.requestAnimationFrame(tick);
      }
    };
    ensureAnimationRef.current = ensureAnimation;

    renderer.on("enterNode", ({ node }) => {
      interactionRef.current.hovered = node;
      interactionRef.current.hoverTarget = 1;
      containerRef.current?.classList.add("is-hovering-node");
      ensureAnimation();
    });
    renderer.on("leaveNode", () => {
      interactionRef.current.hoverTarget = 0;
      containerRef.current?.classList.remove("is-hovering-node");
      ensureAnimation();
    });
    renderer.on("clickNode", ({ node }) => {
      interactionRef.current.selected = node;
      interactionRef.current.selectedPulse = 1;
      onSelectPage(graph.getNodeAttribute(node, "pageId") as string);
      ensureAnimation();
    });
    renderer.on("clickEdge", ({ edge }) => {
      setSelectedEvidence(
        graphEdges.find((item) => item.id === edge)?.evidence ?? null,
      );
    });
    renderer.on("clickStage", () => setSelectedEvidence(null));
    renderer.on("doubleClickStage", ({ event }) => {
      event.preventSigmaDefault();
      renderer
        .getCamera()
        .animatedReset({ duration: reducedMotion ? 0 : 560, easing: "cubicInOut" });
    });

    renderer.on("downNode", ({ node, event }) => {
      interactionRef.current.dragging = node;
      const motion = motionsRef.current[node];
      motion.velocityX = 0;
      motion.velocityY = 0;
      graph.setNodeAttribute(node, "highlighted", true);
      containerRef.current?.classList.add("is-dragging-node");
      event.preventSigmaDefault();
      event.original.preventDefault();
      event.original.stopPropagation();
      ensureAnimation();
    });
    renderer.getMouseCaptor().on("mousemovebody", (event) => {
      const dragged = interactionRef.current.dragging;
      if (!dragged) return;
      const position = renderer.viewportToGraph(event);
      const motion = motionsRef.current[dragged];
      motion.targetX = position.x;
      motion.targetY = position.y;
      motion.delayUntil = 0;
      event.preventSigmaDefault();
      event.original.preventDefault();
      ensureAnimation();
    });
    renderer.getMouseCaptor().on("mouseup", () => {
      const dragged = interactionRef.current.dragging;
      if (dragged) graph.removeNodeAttribute(dragged, "highlighted");
      interactionRef.current.dragging = null;
      containerRef.current?.classList.remove("is-dragging-node");
      ensureAnimation();
    });

    if (!reducedMotion) {
      renderer.getCamera().setState({ x: 0.5, y: 0.5, ratio: 0.82 });
      renderer
        .getCamera()
        .animate(
          { x: 0.5, y: 0.5, ratio: 1.16 },
          { duration: 920, easing: "cubicOut" },
        );
    }
    ensureAnimation();

    return () => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }
      renderer.kill();
      rendererRef.current = null;
      graphRef.current = null;
      ensureAnimationRef.current = () => undefined;
    };
  }, [onSelectPage, reducedMotion]);

  useEffect(() => {
    renderControlsRef.current = {
      nodeScale,
      edgeScale,
      showOrphans,
      localOnly,
    };
    rendererRef.current?.refresh();
  }, [edgeScale, localOnly, nodeScale, showOrphans]);

  useEffect(() => {
    const graph = graphRef.current;
    const renderer = rendererRef.current;
    if (!graph || !renderer) return;
    graph.forEachEdge((edge) => {
      graph.setEdgeAttribute(edge, "type", showArrows ? "arrow" : "line");
    });
    renderer.refresh();
  }, [showArrows]);

  useEffect(() => {
    const graph = graphRef.current;
    const renderer = rendererRef.current;
    if (!graph || !renderer) return;

    const node = graphNodes.find(
      (item) => item.pageId === selectedPageId,
    )?.id;
    if (!node) return;
    const selectionChanged = previousSelectionRef.current !== selectedPageId;
    previousSelectionRef.current = selectedPageId;
    interactionRef.current.selected = node;
    interactionRef.current.selectedPulse = 1;
    ensureAnimationRef.current();

    if (!selectionChanged) return;

    const display = renderer.getNodeDisplayData(node);
    if (!display) return;
    const camera = renderer.getCamera();
    camera.animate(
      {
        x: display.x,
        y: display.y,
        ratio: Math.min(0.88, camera.getState().ratio),
      },
      { duration: reducedMotion ? 0 : 560, easing: "cubicInOut" },
    );
  }, [reducedMotion, selectedPageId]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graphNodes.forEach((node) => {
      const target = finalPositions[node.id];
      const motion = motionsRef.current[node.id];
      motion.targetX = target.x * centerForce;
      motion.targetY = target.y * centerForce;
      motion.delayUntil = 0;
    });
    ensureAnimationRef.current();
  }, [centerForce]);

  const zoom = (direction: "in" | "out") => {
    const camera = rendererRef.current?.getCamera();
    if (!camera) return;
    if (direction === "in") {
      camera.animatedZoom({ duration: reducedMotion ? 0 : 240 });
    } else {
      camera.animatedUnzoom({ duration: reducedMotion ? 0 : 240 });
    }
  };

  const resetCamera = () => {
    rendererRef.current
      ?.getCamera()
      .animatedReset({ duration: reducedMotion ? 0 : 480, easing: "cubicInOut" });
  };

  return (
    <section
      className={`graph-workspace${maximized ? " is-maximized" : ""}`}
      data-testid="graph-panel"
      data-node-count={graphNodes.length}
      data-edge-count={graphEdges.length}
      aria-label="Knowledge graph"
    >
      <div
        ref={containerRef}
        className="sigma-canvas"
        data-testid="sigma-canvas"
        aria-hidden="true"
      />

      {settingsOpen && (
        <aside className="graph-settings" aria-label="图谱设置">
          <div className="graph-settings-title">
            <strong>Graph controls</strong>
            <button
              type="button"
              aria-label="关闭图谱设置"
              onClick={() => setSettingsOpen(false)}
            >
              <X />
            </button>
          </div>
          <label className="graph-search">
            <Search aria-hidden="true" />
            <input placeholder="Search files..." aria-label="搜索图谱" />
          </label>

          <SettingsGroup
            title="Filters"
            icon={<Filter />}
            open={openGroups.has("filters")}
            onToggle={() => toggleGroup("filters")}
          >
            <Toggle checked onChange={() => undefined} label="Existing files only" />
            <Toggle checked={showOrphans} onChange={setShowOrphans} label="Orphans" />
            <Toggle checked={localOnly} onChange={setLocalOnly} label="Local graph" />
          </SettingsGroup>

          <SettingsGroup
            title="Groups"
            icon={<Palette />}
            open={openGroups.has("groups")}
            onToggle={() => toggleGroup("groups")}
          >
            <div className="group-row">
              <i style={{ background: groupColors.source }} />
              <span>Sources</span>
            </div>
            <div className="group-row">
              <i style={{ background: groupColors.entity }} />
              <span>Entities</span>
            </div>
            <div className="group-row">
              <i style={{ background: groupColors.concept }} />
              <span>Concepts</span>
            </div>
          </SettingsGroup>

          <SettingsGroup
            title="Display"
            icon={<Eye />}
            open={openGroups.has("display")}
            onToggle={() => toggleGroup("display")}
          >
            <Toggle checked={showArrows} onChange={setShowArrows} label="Arrows" />
            <label className="graph-range">
              <span>Node size</span>
              <input
                type="range"
                min="0.7"
                max="1.5"
                step="0.05"
                value={nodeScale}
                onChange={(event) => setNodeScale(Number(event.target.value))}
              />
            </label>
            <label className="graph-range">
              <span>Link thickness</span>
              <input
                type="range"
                min="0.6"
                max="2"
                step="0.1"
                value={edgeScale}
                onChange={(event) => setEdgeScale(Number(event.target.value))}
              />
            </label>
            <button className="animate-graph" type="button" onClick={replayLayout}>
              <RefreshCcw />
              Animate
            </button>
          </SettingsGroup>

          <SettingsGroup
            title="Forces"
            icon={<Orbit />}
            open={openGroups.has("forces")}
            onToggle={() => toggleGroup("forces")}
          >
            <label className="graph-range">
              <span>Center force</span>
              <input
                type="range"
                min="0.72"
                max="1.28"
                step="0.02"
                value={centerForce}
                onChange={(event) => setCenterForce(Number(event.target.value))}
              />
            </label>
            <label className="graph-range">
              <span>Repel force</span>
              <input type="range" min="0" max="1" step="0.05" defaultValue="0.58" />
            </label>
            <label className="graph-range">
              <span>Link distance</span>
              <input type="range" min="0" max="1" step="0.05" defaultValue="0.52" />
            </label>
          </SettingsGroup>
        </aside>
      )}

      <div className="graph-tools">
        {!settingsOpen && (
          <button
            type="button"
            aria-label="打开图谱设置"
            title="Graph settings"
            onClick={() => setSettingsOpen(true)}
          >
            <Settings2 />
          </button>
        )}
        <button type="button" aria-label="放大" title="Zoom in" onClick={() => zoom("in")}>
          <Plus />
        </button>
        <button type="button" aria-label="缩小" title="Zoom out" onClick={() => zoom("out")}>
          <Minus />
        </button>
        <button type="button" aria-label="重置视图" title="Reset view" onClick={resetCamera}>
          <Focus />
        </button>
        <button
          type="button"
          aria-label={maximized ? "退出图谱最大化" : "最大化图谱"}
          title={maximized ? "Restore" : "Maximize"}
          onClick={onToggleMaximize}
        >
          {maximized ? <Minimize2 /> : <Maximize2 />}
        </button>
      </div>

      <div className="graph-mode">
        <button
          type="button"
          className={!localOnly ? "is-active" : ""}
          onClick={() => setLocalOnly(false)}
        >
          Global
        </button>
        <button
          type="button"
          className={localOnly ? "is-active" : ""}
          onClick={() => setLocalOnly(true)}
        >
          Local
        </button>
      </div>

      <div className="graph-count">
        <CircleDot aria-hidden="true" />
        <span>4 nodes</span>
        <span>2 links</span>
      </div>

      {selectedEvidence && (
        <button
          className="graph-evidence"
          type="button"
          onClick={() => setSelectedEvidence(null)}
        >
          <SlidersHorizontal />
          <span>{selectedEvidence}</span>
          <X />
        </button>
      )}

      <div className="accessible-node-list" aria-label="图谱节点">
        {graphNodes.map((node) => (
          <button
            key={node.id}
            type="button"
            data-testid={`graph-node-${node.id}`}
            aria-pressed={node.pageId === selectedPageId}
            onClick={() => onSelectPage(node.pageId)}
          >
            {node.label}
          </button>
        ))}
      </div>
    </section>
  );
}
