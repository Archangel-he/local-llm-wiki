import {
  FileText,
  Link2,
  ListTree,
  Maximize2,
  Minimize2,
  PanelRightClose,
  Tags,
} from "lucide-react";
import { useState } from "react";
import { useI18n } from "../i18n";
import type { WikiPage } from "../types";
import { MarkdownPreview } from "./MarkdownPreview";

interface InspectorPanelProps {
  page: WikiPage;
  onClose: () => void;
  maximized: boolean;
  onToggleMaximize: () => void;
  resolveReference: (reference: string) => string | null;
  onSelectPage: (pageId: string) => void;
}

type InspectorTab = "properties" | "backlinks" | "outgoing";

export function InspectorPanel({
  page,
  onClose,
  maximized,
  onToggleMaximize,
  resolveReference,
  onSelectPage,
}: InspectorPanelProps) {
  const { t } = useI18n();
  const [tab, setTab] = useState<InspectorTab>("properties");

  const openReference = (reference: string) => {
    const pageId = resolveReference(reference);
    if (pageId && pageId !== page.id) onSelectPage(pageId);
  };

  const referenceTarget = (reference: string) => {
    const pageId = resolveReference(reference);
    return pageId && pageId !== page.id ? pageId : null;
  };

  return (
    <aside
      className={`right-sidebar${maximized ? " is-maximized" : ""}`}
      data-testid="wiki-panel"
      data-page-id={page.id}
    >
      <div className="right-tab-strip" role="tablist" aria-label={t("wiki")}>
        {[
          {
            id: "properties" as const,
            label: t("properties"),
            icon: <ListTree />,
          },
          {
            id: "backlinks" as const,
            label: t("backlinks"),
            icon: <Link2 />,
          },
          {
            id: "outgoing" as const,
            label: t("outgoingLinks"),
            icon: <Tags />,
          },
        ].map((item) => (
          <button
            className={tab === item.id ? "is-active" : ""}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            key={item.id}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
        <span className="right-tab-spacer" />
        <button
          className="right-panel-action"
          type="button"
          title={maximized ? t("restore") : t("maximize")}
          aria-label={maximized ? t("restore") : t("maximize")}
          onClick={onToggleMaximize}
        >
          {maximized ? <Minimize2 /> : <Maximize2 />}
        </button>
        <button
          className="right-panel-action"
          type="button"
          title={t("closeDetails")}
          aria-label={t("closeDetails")}
          onClick={onClose}
        >
          <PanelRightClose />
        </button>
      </div>

      <article className="inspector-content">
        <div className="inspector-title">
          <FileText aria-hidden="true" />
          <div>
            <span>
              {tab === "properties"
                ? t("properties")
                : tab === "backlinks"
                  ? t("backlinks")
                  : t("outgoingLinks")}
            </span>
            <h2 data-testid="wiki-title">{page.title}</h2>
          </div>
        </div>

        {tab === "properties" && (
          <>
            <div className="property-grid">
              <span>{t("aliases")}</span>
              <strong>{page.aliases.length ? page.aliases.join(", ") : t("none")}</strong>
              <span>{t("type")}</span>
              <strong>{page.type}</strong>
              <span>{t("status")}</span>
              <strong>{page.status.replace("_", " ")}</strong>
              <span>{t("tags")}</span>
              <strong>{page.tags.map((tag) => `#${tag}`).join(" ")}</strong>
              <span>{t("revision")}</span>
              <strong>{page.revision}</strong>
            </div>
            <div className="note-preview">
              {page.systemView && (
                <span className="system-view-badge">
                  {t("readOnlySystemView")}
                </span>
              )}
              <p className="note-lead">{page.summary}</p>
              <MarkdownPreview blocks={page.body} />
              {page.sources.length > 0 && <h3>{t("sources")}</h3>}
              {page.sources.map((source) =>
                referenceTarget(source) ? (
                  <button
                    className="internal-link"
                    type="button"
                    key={source}
                    onClick={() => openReference(source)}
                  >
                    {source}
                  </button>
                ) : (
                  <span className="internal-link is-static" key={source}>
                    {source}
                  </span>
                ),
              )}
            </div>
          </>
        )}

        {tab === "backlinks" && (
          <div className="link-pane">
            <div className="link-pane-heading">
              <span>{t("linkedMentions")}</span>
              <span>{page.backlinks.length}</span>
            </div>
            {page.backlinks.length ? (
              page.backlinks.map((link) => {
                const target = referenceTarget(link);
                const content = (
                  <>
                    <FileText />
                    <span>
                      <strong>{link}</strong>
                      <small>{t("backlinks")}</small>
                    </span>
                  </>
                );
                return target ? (
                  <button
                    type="button"
                    className="mention-card"
                    key={link}
                    onClick={() => openReference(link)}
                  >
                    {content}
                  </button>
                ) : (
                  <div className="mention-card is-static" key={link}>
                    {content}
                  </div>
                );
              })
            ) : (
              <p className="empty-pane">{t("noBacklinks")}</p>
            )}
            <div className="link-pane-heading unlinked">
              <span>{t("unlinkedMentions")}</span>
              <span>0</span>
            </div>
          </div>
        )}

        {tab === "outgoing" && (
          <div className="link-pane">
            <div className="link-pane-heading">
              <span>{t("outgoingLinks")}</span>
              <span>{page.sources.length}</span>
            </div>
            {page.sources.map((source) => {
              const target = referenceTarget(source);
              const content = (
                <>
                  <Link2 />
                  <span>
                    <strong>{source.split(" · ")[0]}</strong>
                    <small>{t("sourceCitation")}</small>
                  </span>
                </>
              );
              return target ? (
                <button
                  type="button"
                  className="mention-card"
                  key={source}
                  onClick={() => openReference(source)}
                >
                  {content}
                </button>
              ) : (
                <div className="mention-card is-static" key={source}>
                  {content}
                </div>
              );
            })}
          </div>
        )}
      </article>
    </aside>
  );
}
