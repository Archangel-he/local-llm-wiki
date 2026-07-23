import {
  Bot,
  ChevronDown,
  Command,
  Hexagon,
  Minus,
  MoreHorizontal,
  Network,
  PanelRightOpen,
  Plus,
  Search,
  Square,
  X,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { AskPanel } from "./components/AskPanel";
import { FileExplorer } from "./components/FileExplorer";
import { GraphWorkspace } from "./components/GraphWorkspace";
import { HealthPopover } from "./components/HealthPopover";
import { InspectorPanel } from "./components/InspectorPanel";
import { Ribbon } from "./components/Ribbon";
import { SettingsDialog } from "./components/SettingsDialog";
import {
  defaultWorkspace,
  graphEdges,
  graphNodes,
  modelProfileFixture,
  wikiPages,
} from "./fixtures/workspace";
import { usePanelResize } from "./hooks/usePanelResize";

type MaximizedPanel = "graph" | "ask" | "wiki" | null;

function App() {
  const [selectedPageId, setSelectedPageId] = useState("page-a");
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [askOpen, setAskOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [healthOpen, setHealthOpen] = useState(false);
  const [maximizedPanel, setMaximizedPanel] = useState<MaximizedPanel>(null);

  const leftPanel = usePanelResize({
    initial: 248,
    min: 200,
    max: 360,
    axis: "x",
  });
  const rightPanel = usePanelResize({
    initial: 310,
    min: 250,
    max: 480,
    axis: "x",
    invert: true,
  });
  const askPanel = usePanelResize({
    initial: 218,
    min: 160,
    max: 380,
    axis: "y",
    invert: true,
  });

  const selectedPage = useMemo(
    () =>
      wikiPages.find((page) => page.id === selectedPageId) ?? wikiPages[0],
    [selectedPageId],
  );

  const selectPage = useCallback((pageId: string) => {
    setSelectedPageId(pageId);
  }, []);

  const toggleMaximized = (panel: Exclude<MaximizedPanel, null>) => {
    setMaximizedPanel((current) => (current === panel ? null : panel));
  };

  return (
    <main
      className={`obsidian-app${leftOpen ? " has-left-sidebar" : ""}${rightOpen ? " has-right-sidebar" : ""}${askOpen ? " has-ask-panel" : ""}`}
      data-testid="workspace"
      style={
        {
          "--left-sidebar-width": `${leftPanel.size}px`,
          "--right-sidebar-width": `${rightPanel.size}px`,
          "--ask-panel-height": `${askPanel.size}px`,
        } as React.CSSProperties
      }
    >
      <header className="titlebar">
        <div className="titlebar-brand">
          <Hexagon aria-hidden="true" />
          <span>{defaultWorkspace.name}</span>
        </div>

        <button className="global-search" type="button">
          <Search aria-hidden="true" />
          <span>Search...</span>
          <kbd>
            <Command aria-hidden="true" />K
          </kbd>
        </button>

        <span className="window-document">local-llm-wiki</span>

        <div className="window-controls" aria-hidden="true">
          <button type="button" tabIndex={-1}>
            <Minus />
          </button>
          <button type="button" tabIndex={-1}>
            <Square />
          </button>
          <button type="button" tabIndex={-1}>
            <X />
          </button>
        </div>
      </header>

      <div className="workbench">
        <Ribbon
          leftOpen={leftOpen}
          onToggleLeft={() => setLeftOpen((value) => !value)}
          onToggleAsk={() => setAskOpen((value) => !value)}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        {leftOpen && (
          <>
            <FileExplorer
              selectedPageId={selectedPageId}
              onSelectPage={selectPage}
            />
            <div
              className="pane-resizer vertical"
              role="separator"
              aria-label="调整文件栏宽度"
              aria-orientation="vertical"
              aria-valuemin={200}
              aria-valuemax={360}
              aria-valuenow={leftPanel.size}
              tabIndex={0}
              onPointerDown={leftPanel.onPointerDown}
              onKeyDown={leftPanel.onKeyDown}
              data-testid="left-resizer"
            />
          </>
        )}

        <section className="editor-region">
          <div className="workspace-tabs">
            <button className="workspace-tab is-active" type="button">
              <Network aria-hidden="true" />
              <span>Graph view</span>
              <X className="tab-close" aria-hidden="true" />
            </button>
            <span className="workspace-tabs-spacer" />
            <button type="button" aria-label="新建标签页" title="New tab">
              <Plus />
            </button>
            <button type="button" aria-label="标签页菜单" title="Tab menu">
              <ChevronDown />
            </button>
            <button type="button" aria-label="更多选项" title="More options">
              <MoreHorizontal />
            </button>
            {!rightOpen && (
              <button
                className="right-sidebar-reopen"
                type="button"
                aria-label="展开右侧栏"
                title="Open right sidebar"
                onClick={() => setRightOpen(true)}
              >
                <PanelRightOpen />
              </button>
            )}
          </div>

          <div className="editor-stack">
            <GraphWorkspace
              selectedPageId={selectedPageId}
              onSelectPage={selectPage}
              maximized={maximizedPanel === "graph"}
              onToggleMaximize={() => toggleMaximized("graph")}
            />

            {askOpen && (
              <div
                className="pane-resizer horizontal"
                role="separator"
                aria-label="调整问答区域高度"
                aria-orientation="horizontal"
                aria-valuemin={160}
                aria-valuemax={380}
                aria-valuenow={askPanel.size}
                tabIndex={0}
                onPointerDown={askPanel.onPointerDown}
                onKeyDown={askPanel.onKeyDown}
                data-testid="query-resizer"
              />
            )}

            <AskPanel
              open={askOpen}
              onToggle={() => setAskOpen((value) => !value)}
              maximized={maximizedPanel === "ask"}
              onToggleMaximize={() => toggleMaximized("ask")}
            />
          </div>
        </section>

        {rightOpen && (
          <>
            <div
              className="pane-resizer vertical"
              role="separator"
              aria-label="调整 Wiki 栏宽度"
              aria-orientation="vertical"
              aria-valuemin={250}
              aria-valuemax={480}
              aria-valuenow={rightPanel.size}
              tabIndex={0}
              onPointerDown={rightPanel.onPointerDown}
              onKeyDown={rightPanel.onKeyDown}
              data-testid="right-resizer"
            />
            <InspectorPanel
              page={selectedPage}
              onClose={() => setRightOpen(false)}
              maximized={maximizedPanel === "wiki"}
              onToggleMaximize={() => toggleMaximized("wiki")}
            />
          </>
        )}
      </div>

      <footer className="statusbar">
        <div className="statusbar-left">
          <button type="button" title="Command palette">
            <Command aria-hidden="true" />
          </button>
          <span>Local vault</span>
          <span className="status-separator" />
          <span>{selectedPage.title}</span>
        </div>
        <div className="statusbar-right">
          <button
            className="model-status"
            type="button"
            onClick={() => setSettingsOpen(true)}
          >
            <Bot aria-hidden="true" />
            <span>
              {modelProfileFixture.name} · {modelProfileFixture.modelId}
            </span>
            <i className="status-dot degraded" aria-hidden="true" />
          </button>
          <span>{graphNodes.length} nodes</span>
          <span>{graphEdges.length} links</span>
          <div className="health-anchor">
            <button
              className="health-trigger"
              type="button"
              aria-expanded={healthOpen}
              onClick={() => setHealthOpen((value) => !value)}
              data-testid="health-trigger"
            >
              <i className="status-dot degraded" aria-hidden="true" />
              Degraded
            </button>
            <HealthPopover open={healthOpen} />
          </div>
        </div>
      </footer>

      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </main>
  );
}

export default App;
