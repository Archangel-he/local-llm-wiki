import {
  Bot,
  BookOpen,
  Hexagon,
  MessageSquare,
  Network,
  PanelRightOpen,
  Settings,
} from "lucide-react";
import {
  useCallback,
  useMemo,
  useState,
} from "react";
import { AskPanel } from "./components/AskPanel";
import { ExportPreviewDialog } from "./components/ExportPreviewDialog";
import { FileExplorer } from "./components/FileExplorer";
import { GraphWorkspace } from "./components/GraphWorkspace";
import { HealthPopover } from "./components/HealthPopover";
import { InspectorPanel } from "./components/InspectorPanel";
import { SettingsDialog } from "./components/SettingsDialog";
import { defaultWorkspace } from "./fixtures/workspace";
import { LanguageProvider, useI18n } from "./i18n";
import { usePanelResize } from "./hooks/usePanelResize";
import { useMvp1Workspace } from "./mvp1/useMvp1Workspace";

type MaximizedPanel = "graph" | "ask" | "wiki" | null;

function WorkspaceApp() {
  const { t } = useI18n();
  const workspace = useMvp1Workspace();
  const loadSourcePage = workspace.loadSourcePage;
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

  const currentPageId = useMemo(
    () =>
      workspace.data.pages.some((page) => page.id === selectedPageId)
        ? selectedPageId
        : workspace.data.pages[0]?.id ?? selectedPageId,
    [selectedPageId, workspace.data.pages],
  );
  const selectedPage = useMemo(
    () => workspace.data.pages.find((page) => page.id === currentPageId),
    [currentPageId, workspace.data.pages],
  );
  const defaultProfile = workspace.profiles.find(
    (profile) => profile.id === workspace.defaultProfileId,
  );

  const selectPage = useCallback(
    (pageId: string) => {
      setSelectedPageId(pageId);
      setRightOpen(true);
      void loadSourcePage(pageId);
    },
    [loadSourcePage],
  );

  const resolveReference = useCallback(
    (reference: string) => {
      const token = reference.split(" · ")[0].trim();
      return (
        workspace.data.pages.find(
          (page) =>
            page.id === token ||
            page.id === `raw-${token}` ||
            page.title === token,
        )?.id ?? null
      );
    },
    [workspace.data.pages],
  );

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

        <span className="window-document">
          {selectedPage?.title ?? t("knowledgeGraph")}
        </span>

        <nav className="titlebar-actions" aria-label={t("primaryActions")}>
          <button
            type="button"
            className={leftOpen ? "is-active" : ""}
            aria-pressed={leftOpen}
            title={leftOpen ? t("hideLibrary") : t("showLibrary")}
            onClick={() => setLeftOpen((value) => !value)}
          >
            <BookOpen />
            <span>{t("library")}</span>
          </button>
          <button
            type="button"
            className={askOpen ? "is-active" : ""}
            aria-pressed={askOpen}
            title={askOpen ? t("hideAsk") : t("showAsk")}
            onClick={() => setAskOpen((value) => !value)}
          >
            <MessageSquare />
            <span>{t("askPanel")}</span>
          </button>
          <button
            type="button"
            data-testid="model-settings-trigger"
            title={t("settings")}
            onClick={() => setSettingsOpen(true)}
          >
            <Settings />
            <span>{t("settings")}</span>
          </button>
        </nav>
      </header>

      <div className="workbench">
        {leftOpen && (
          <>
            <FileExplorer
              selectedPageId={currentPageId}
              onSelectPage={selectPage}
              sections={workspace.treeSections}
              jobs={workspace.data.jobs}
              uploadMessage={workspace.uploadMessage}
              uploadError={workspace.uploadError}
              uploading={workspace.uploading}
              onUploadSource={workspace.uploadSource}
              onExportPreview={workspace.loadExportPreview}
              onRetryJob={workspace.retryJob}
              onCancelJob={workspace.cancelJob}
            />
            <div
              className="pane-resizer vertical"
              role="separator"
              aria-label={t("resizeLibrary")}
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
            <div className="workspace-heading">
              <Network aria-hidden="true" />
              <strong>{t("knowledgeGraph")}</strong>
            </div>
            {!rightOpen && (
              <button
                className="right-sidebar-reopen"
                type="button"
                title={t("showDetails")}
                onClick={() => setRightOpen(true)}
              >
                <PanelRightOpen />
                <span>{t("showDetails")}</span>
              </button>
            )}
          </div>

          <div className="editor-stack">
            <GraphWorkspace
              graphNodes={workspace.data.graphNodes}
              graphEdges={workspace.data.graphEdges}
              selectedPageId={currentPageId}
              onSelectPage={selectPage}
              maximized={maximizedPanel === "graph"}
              onToggleMaximize={() => toggleMaximized("graph")}
            />

            {askOpen && (
              <div
                className="pane-resizer horizontal"
                role="separator"
                aria-label={t("resizeAsk")}
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
              maximized={maximizedPanel === "ask"}
              onToggleMaximize={() => toggleMaximized("ask")}
              model={defaultProfile}
            />
          </div>
        </section>

        {rightOpen && selectedPage && (
          <>
            <div
              className="pane-resizer vertical"
              role="separator"
              aria-label={t("resizeWiki")}
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
              resolveReference={resolveReference}
              onSelectPage={selectPage}
            />
          </>
        )}
      </div>

      <footer className="statusbar">
        <div className="statusbar-left">
          <span>{t("localVault")}</span>
          <span className="status-separator" />
          <span>{selectedPage?.title ?? t("loadingVault")}</span>
        </div>
        <div className="statusbar-right">
          <span className="model-status">
            <Bot aria-hidden="true" />
            <span>
              {defaultProfile
                ? `${defaultProfile.displayName} · ${defaultProfile.modelName}`
                : t("noDefaultModel")}
            </span>
            <i
              className={`status-dot ${defaultProfile?.status === "active" ? "ok" : "degraded"}`}
              aria-hidden="true"
            />
          </span>
          <span>
            {workspace.data.graphNodes.length} {t("nodes")}
          </span>
          <span>
            {workspace.data.graphEdges.length} {t("links")}
          </span>
          <div className="health-anchor">
            <button
              className="health-trigger"
              type="button"
              aria-expanded={healthOpen}
              onClick={() => setHealthOpen((value) => !value)}
              data-testid="health-trigger"
            >
              <i className="status-dot degraded" aria-hidden="true" />
              {t("systemHealth")}
            </button>
            <HealthPopover open={healthOpen} />
          </div>
        </div>
      </footer>

      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        profiles={workspace.profiles}
        defaultProfileId={workspace.defaultProfileId}
        onCreateProfile={workspace.createProfile}
        onUpdateProfile={workspace.updateProfile}
        onDeleteProfile={workspace.deleteProfile}
        onDiscoverModels={workspace.discoverModels}
        onTestProfile={workspace.testProfile}
        onSetDefaultProfile={workspace.setDefaultProfile}
      />
      <ExportPreviewDialog
        preview={workspace.exportPreview}
        job={workspace.exportJob}
        error={workspace.exportError}
        downloadUrl={workspace.exportDownloadUrl}
        onStartExport={workspace.startExport}
        onClose={workspace.closeExportPreview}
      />
    </main>
  );
}

export default function App() {
  return (
    <LanguageProvider>
      <WorkspaceApp />
    </LanguageProvider>
  );
}
