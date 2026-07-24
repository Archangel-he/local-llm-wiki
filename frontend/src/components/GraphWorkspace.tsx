import {
  CircleDot,
  Focus,
  Maximize2,
  Minimize2,
  Minus,
  Plus,
  RefreshCcw,
  Search,
  Settings2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n";
import type { GraphEdge, GraphNode } from "../types";

interface GraphWorkspaceProps {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  selectedPageId: string;
  onSelectPage: (pageId: string) => void;
  maximized: boolean;
  onToggleMaximize: () => void;
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

function uniqueNodeLabels(nodes: GraphNode[]) {
  const counts = new Map<string, number>();
  for (const node of nodes) {
    counts.set(node.label, (counts.get(node.label) ?? 0) + 1);
  }
  return nodes.map((node) => ({
    ...node,
    label:
      (counts.get(node.label) ?? 0) > 1
        ? `${node.label} · ${node.id.slice(0, 8)}`
        : node.label,
  }));
}

export function GraphWorkspace({
  graphNodes,
  graphEdges,
  selectedPageId,
  onSelectPage,
  maximized,
  onToggleMaximize,
}: GraphWorkspaceProps) {
  const { t } = useI18n();
  const reproFrameRef = useRef<HTMLIFrameElement>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showOrphans, setShowOrphans] = useState(true);
  const [showArrows, setShowArrows] = useState(false);
  const [nodeScale, setNodeScale] = useState(0.7);
  const [edgeScale, setEdgeScale] = useState(1.15);
  const [centerForce, setCenterForce] = useState(0.1);
  const [repelForce, setRepelForce] = useState(1000);
  const [linkStrength, setLinkStrength] = useState(1);
  const [linkDistance, setLinkDistance] = useState(180);
  const [localOnly, setLocalOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [searchMiss, setSearchMiss] = useState(false);

  const displayNodes = useMemo(
    () => uniqueNodeLabels(graphNodes),
    [graphNodes],
  );
  const selectedNode = useMemo(
    () => displayNodes.find((node) => node.pageId === selectedPageId),
    [displayNodes, selectedPageId],
  );

  const visibleGraph = useMemo(() => {
    const connectedIds = new Set<string>();
    for (const edge of graphEdges) {
      connectedIds.add(edge.source);
      connectedIds.add(edge.target);
    }

    let visibleIds = new Set(
      displayNodes
        .filter((node) => showOrphans || connectedIds.has(node.id))
        .map((node) => node.id),
    );

    if (localOnly && selectedNode) {
      const localIds = new Set([selectedNode.id]);
      for (const edge of graphEdges) {
        if (edge.source === selectedNode.id) localIds.add(edge.target);
        if (edge.target === selectedNode.id) localIds.add(edge.source);
      }
      visibleIds = new Set([...visibleIds].filter((id) => localIds.has(id)));
    }

    return {
      nodes: displayNodes.filter((node) => visibleIds.has(node.id)),
      edges: graphEdges.filter(
        (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
      ),
    };
  }, [displayNodes, graphEdges, localOnly, selectedNode, showOrphans]);

  const postToGraph = useCallback((message: object) => {
    reproFrameRef.current?.contentWindow?.postMessage(
      message,
      window.location.origin,
    );
  }, []);

  const updateRange = useCallback((id: string, value: number) => {
    const input = reproFrameRef.current?.contentDocument?.getElementById(
      id,
    ) as HTMLInputElement | null;
    if (!input) return;
    input.value = String(value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, []);

  const syncGraph = useCallback(() => {
    postToGraph({
      type: "graph-data",
      nodes: visibleGraph.nodes.map((node) => ({
        id: node.id,
        label: node.label,
        pageId: node.pageId,
        weight: node.size,
        x: node.x * 180,
        y: node.y * 180,
      })),
      links: visibleGraph.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
      })),
    });
  }, [postToGraph, visibleGraph]);

  const syncOptions = useCallback(() => {
    postToGraph({ type: "graph-options", showArrows });
  }, [postToGraph, showArrows]);

  const syncControls = useCallback(() => {
    updateRange("node-size", nodeScale);
    updateRange("link-thickness", edgeScale);
    updateRange("center", centerForce);
    updateRange("repel", repelForce);
    updateRange("link-strength", linkStrength);
    updateRange("link-distance", linkDistance);
  }, [
    centerForce,
    edgeScale,
    linkDistance,
    linkStrength,
    nodeScale,
    repelForce,
    updateRange,
  ]);

  useEffect(() => {
    syncGraph();
  }, [syncGraph]);

  useEffect(() => {
    syncOptions();
  }, [syncOptions]);

  useEffect(() => {
    postToGraph({ type: "graph-focus-node", pageId: selectedPageId });
  }, [postToGraph, selectedPageId, visibleGraph]);

  useEffect(() => {
    const handleGraphMessage = (event: MessageEvent) => {
      if (
        event.origin !== window.location.origin ||
        event.source !== reproFrameRef.current?.contentWindow ||
        event.data?.type !== "graph-node-select"
      ) {
        return;
      }
      const node = graphNodes.find(
        (candidate) =>
          candidate.id === event.data.nodeId &&
          candidate.pageId === event.data.pageId,
      );
      if (node) onSelectPage(node.pageId);
    };

    window.addEventListener("message", handleGraphMessage);
    return () => window.removeEventListener("message", handleGraphMessage);
  }, [graphNodes, onSelectPage]);

  const triggerHiddenButton = (id: "reheat" | "reset") => {
    const button = reproFrameRef.current?.contentDocument?.getElementById(
      id,
    ) as HTMLButtonElement | null;
    button?.click();
  };

  const cameraAction = (action: "zoom-in" | "zoom-out" | "fit") => {
    postToGraph({ type: "graph-camera", action });
  };

  const selectMode = (nextLocalOnly: boolean) => {
    if (nextLocalOnly && !selectedNode && displayNodes[0]) {
      onSelectPage(displayNodes[0].pageId);
    }
    setLocalOnly(nextLocalOnly);
  };

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) {
      setSearchMiss(false);
      return;
    }
    const match = displayNodes.find((node) =>
      node.label.toLocaleLowerCase().includes(normalized),
    );
    setSearchMiss(!match);
    if (match) onSelectPage(match.pageId);
  };

  return (
    <section
      className={`graph-workspace${maximized ? " is-maximized" : ""}`}
      data-testid="graph-panel"
      data-node-count={visibleGraph.nodes.length}
      data-edge-count={visibleGraph.edges.length}
      aria-label={t("knowledgeGraph")}
    >
      <div className="sigma-canvas" data-testid="sigma-canvas">
        <iframe
          ref={reproFrameRef}
          className="repro-graph-frame"
          data-testid="graph-repro-frame"
          src="/obsidian-graph-repro/index.html"
          title={t("knowledgeGraph")}
          onLoad={() => {
            syncGraph();
            syncControls();
            syncOptions();
            postToGraph({ type: "graph-focus-node", pageId: selectedPageId });
          }}
        />
      </div>

      {settingsOpen && (
        <aside className="graph-settings" aria-label={t("graphControls")}>
          <div className="graph-settings-title">
            <strong>{t("graphControls")}</strong>
            <button
              type="button"
              aria-label={t("closeGraphControls")}
              title={t("closeGraphControls")}
              onClick={() => setSettingsOpen(false)}
            >
              <X />
            </button>
          </div>

          <form className="graph-search" onSubmit={submitSearch}>
            <Search aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setSearchMiss(false);
              }}
              placeholder={t("searchGraph")}
              aria-label={t("searchGraph")}
              list="graph-node-options"
            />
            <button type="submit">{t("search")}</button>
            <datalist id="graph-node-options">
              {displayNodes.map((node) => (
                <option value={node.label} key={node.id} />
              ))}
            </datalist>
          </form>
          {searchMiss && <p className="graph-search-message">{t("noGraphMatch")}</p>}

          <section className="graph-settings-section">
            <h3>{t("display")}</h3>
            <Toggle
              checked={showOrphans}
              onChange={setShowOrphans}
              label={t("orphans")}
            />
            <Toggle
              checked={showArrows}
              onChange={setShowArrows}
              label={t("arrows")}
            />
            <label className="graph-range">
              <span>{t("nodeSize")}</span>
              <input
                type="range"
                min="0.45"
                max="1.2"
                step="0.05"
                value={nodeScale}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setNodeScale(value);
                  updateRange("node-size", value);
                }}
              />
            </label>
            <label className="graph-range">
              <span>{t("linkThickness")}</span>
              <input
                type="range"
                min="0.6"
                max="2"
                step="0.1"
                value={edgeScale}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setEdgeScale(value);
                  updateRange("link-thickness", value);
                }}
              />
            </label>
          </section>

          <section className="graph-settings-section">
            <h3>{t("layout")}</h3>
            {[
              {
                id: "center",
                label: t("centerForce"),
                min: 0,
                max: 0.3,
                step: 0.01,
                value: centerForce,
                setValue: setCenterForce,
              },
              {
                id: "repel",
                label: t("repelForce"),
                min: 100,
                max: 3000,
                step: 50,
                value: repelForce,
                setValue: setRepelForce,
              },
              {
                id: "link-strength",
                label: t("linkStrength"),
                min: 0,
                max: 2,
                step: 0.05,
                value: linkStrength,
                setValue: setLinkStrength,
              },
              {
                id: "link-distance",
                label: t("linkDistance"),
                min: 50,
                max: 350,
                step: 5,
                value: linkDistance,
                setValue: setLinkDistance,
              },
            ].map((control) => (
              <label className="graph-range" key={control.id}>
                <span>{control.label}</span>
                <input
                  type="range"
                  min={control.min}
                  max={control.max}
                  step={control.step}
                  value={control.value}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    control.setValue(value);
                    updateRange(control.id, value);
                  }}
                />
              </label>
            ))}
            <div className="graph-force-actions">
              <button
                className="animate-graph"
                type="button"
                onClick={() => triggerHiddenButton("reheat")}
              >
                <RefreshCcw />
                {t("reheatLayout")}
              </button>
              <button
                className="animate-graph"
                type="button"
                onClick={() => triggerHiddenButton("reset")}
              >
                <Focus />
                {t("resetPositions")}
              </button>
            </div>
          </section>
        </aside>
      )}

      <div className="graph-tools" aria-label={t("knowledgeGraph")}>
        {!settingsOpen && (
          <button
            type="button"
            title={t("graphControls")}
            onClick={() => setSettingsOpen(true)}
          >
            <Settings2 />
            <span>{t("openGraphControls")}</span>
          </button>
        )}
        <button
          type="button"
          title={t("zoomIn")}
          onClick={() => cameraAction("zoom-in")}
        >
          <Plus />
          <span>{t("zoomIn")}</span>
        </button>
        <button
          type="button"
          title={t("zoomOut")}
          onClick={() => cameraAction("zoom-out")}
        >
          <Minus />
          <span>{t("zoomOut")}</span>
        </button>
        <button
          type="button"
          title={t("fitGraph")}
          onClick={() => cameraAction("fit")}
        >
          <Focus />
          <span>{t("fitGraph")}</span>
        </button>
        <button
          type="button"
          title={maximized ? t("restore") : t("maximize")}
          onClick={onToggleMaximize}
        >
          {maximized ? <Minimize2 /> : <Maximize2 />}
          <span>{maximized ? t("restore") : t("maximize")}</span>
        </button>
      </div>

      <div className="graph-mode" role="group" aria-label={t("localGraph")}>
        <button
          type="button"
          className={!localOnly ? "is-active" : ""}
          aria-pressed={!localOnly}
          onClick={() => selectMode(false)}
        >
          {t("global")}
        </button>
        <button
          type="button"
          className={localOnly ? "is-active" : ""}
          aria-pressed={localOnly}
          onClick={() => selectMode(true)}
        >
          {t("local")}
        </button>
      </div>

      <div className="graph-count">
        <CircleDot aria-hidden="true" />
        <span>
          {visibleGraph.nodes.length} {t("nodes")}
        </span>
        <span>
          {visibleGraph.edges.length} {t("links")}
        </span>
      </div>

      <div className="accessible-node-list" aria-label={t("knowledgeGraph")}>
        {visibleGraph.nodes.map((node) => (
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
