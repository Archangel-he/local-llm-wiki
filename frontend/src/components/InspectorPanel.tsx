import {
  FileText,
  Link2,
  ListTree,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  PanelRightClose,
  Tags,
} from "lucide-react";
import { useState } from "react";
import type { WikiPage } from "../types";

interface InspectorPanelProps {
  page: WikiPage;
  onClose: () => void;
  maximized: boolean;
  onToggleMaximize: () => void;
}

type InspectorTab = "properties" | "backlinks" | "outgoing";

export function InspectorPanel({
  page,
  onClose,
  maximized,
  onToggleMaximize,
}: InspectorPanelProps) {
  const [tab, setTab] = useState<InspectorTab>("properties");

  return (
    <aside
      className={`right-sidebar${maximized ? " is-maximized" : ""}`}
      data-testid="wiki-panel"
      data-page-id={page.id}
    >
      <div className="right-tab-strip" role="tablist" aria-label="右侧栏">
        <button
          className={tab === "properties" ? "is-active" : ""}
          type="button"
          role="tab"
          aria-selected={tab === "properties"}
          onClick={() => setTab("properties")}
          title="Properties"
        >
          <ListTree />
        </button>
        <button
          className={tab === "backlinks" ? "is-active" : ""}
          type="button"
          role="tab"
          aria-selected={tab === "backlinks"}
          onClick={() => setTab("backlinks")}
          title="Backlinks"
        >
          <Link2 />
        </button>
        <button
          className={tab === "outgoing" ? "is-active" : ""}
          type="button"
          role="tab"
          aria-selected={tab === "outgoing"}
          onClick={() => setTab("outgoing")}
          title="Outgoing links"
        >
          <Tags />
        </button>
        <span className="right-tab-spacer" />
        <button
          type="button"
          title={maximized ? "Restore" : "Maximize"}
          aria-label={maximized ? "退出 Wiki 最大化" : "最大化 Wiki"}
          onClick={onToggleMaximize}
        >
          {maximized ? <Minimize2 /> : <Maximize2 />}
        </button>
        <button type="button" title="More options" aria-label="更多选项">
          <MoreHorizontal />
        </button>
        <button type="button" title="Close" aria-label="关闭右侧栏" onClick={onClose}>
          <PanelRightClose />
        </button>
      </div>

      <article className="inspector-content">
        <div className="inspector-title">
          <FileText aria-hidden="true" />
          <div>
            <span>{tab === "properties" ? "Properties" : tab === "backlinks" ? "Backlinks" : "Outgoing links"}</span>
            <h2 data-testid="wiki-title">{page.title}</h2>
          </div>
        </div>

        {tab === "properties" && (
          <>
            <div className="property-grid">
              <span>aliases</span>
              <strong>{page.aliases.length ? page.aliases.join(", ") : "—"}</strong>
              <span>type</span>
              <strong>{page.type}</strong>
              <span>status</span>
              <strong>{page.status.replace("_", " ")}</strong>
              <span>tags</span>
              <strong>{page.tags.map((tag) => `#${tag}`).join(" ")}</strong>
              <span>revision</span>
              <strong>{page.revision}</strong>
            </div>
            <div className="note-preview">
              <p className="note-lead">{page.summary}</p>
              {page.body.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
              <h3>Sources</h3>
              {page.sources.map((source) => (
                <button className="internal-link" type="button" key={source}>
                  {source}
                </button>
              ))}
            </div>
          </>
        )}

        {tab === "backlinks" && (
          <div className="link-pane">
            <div className="link-pane-heading">
              <span>Linked mentions</span>
              <span>{page.backlinks.length}</span>
            </div>
            {page.backlinks.length ? (
              page.backlinks.map((link) => (
                <button type="button" className="mention-card" key={link}>
                  <FileText />
                  <span>
                    <strong>{link}</strong>
                    <small>… links to [[{page.title}]]</small>
                  </span>
                </button>
              ))
            ) : (
              <p className="empty-pane">This page is an orphan. No backlinks found.</p>
            )}
            <div className="link-pane-heading unlinked">
              <span>Unlinked mentions</span>
              <span>0</span>
            </div>
          </div>
        )}

        {tab === "outgoing" && (
          <div className="link-pane">
            <div className="link-pane-heading">
              <span>Links</span>
              <span>{page.sources.length}</span>
            </div>
            {page.sources.map((source) => (
              <button type="button" className="mention-card" key={source}>
                <Link2 />
                <span>
                  <strong>{source.split(" · ")[0]}</strong>
                  <small>Source citation</small>
                </span>
              </button>
            ))}
          </div>
        )}
      </article>
    </aside>
  );
}
