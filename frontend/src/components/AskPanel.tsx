import { Bot, Maximize2, Minimize2, Send, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { useI18n } from "../i18n";
import type { ModelProfile } from "../mvp1/contracts";

interface AskPanelProps {
  open: boolean;
  maximized: boolean;
  onToggleMaximize: () => void;
  model?: ModelProfile;
}

export function AskPanel({
  open,
  maximized,
  onToggleMaximize,
  model,
}: AskPanelProps) {
  const { language, t } = useI18n();
  const [question, setQuestion] = useState("");
  const [answered, setAnswered] = useState(false);
  const [scope, setScope] = useState("current");
  const modelLabel = model
    ? `${model.displayName} · ${model.modelName}`
    : t("noDefaultModel");

  if (!open) return null;

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    setAnswered(true);
  };

  return (
    <section
      className={`ask-panel is-open${maximized ? " is-maximized" : ""}`}
      data-testid="query-panel"
      aria-label={t("askLocalWiki")}
    >
      <header className="ask-handle">
        <div className="ask-title">
          <Sparkles aria-hidden="true" />
          <span>{t("llmWikiAnswer")}</span>
          <small data-testid="query-model">{modelLabel}</small>
        </div>
        <button
          className="ask-maximize"
          type="button"
          title={maximized ? t("restore") : t("maximize")}
          aria-label={maximized ? t("restore") : t("maximize")}
          onClick={onToggleMaximize}
        >
          {maximized ? <Minimize2 /> : <Maximize2 />}
        </button>
      </header>

      <div className="ask-body">
        <div className="ask-thread" aria-live="polite">
          {answered ? (
            <article className="answer-message" data-testid="query-notice">
              <div className="assistant-avatar">
                <Bot aria-hidden="true" />
              </div>
              <div>
                <span className="answer-label">{t("llmWikiAnswer")}</span>
                <p>
                  {language === "zh"
                    ? `当前版本尚未执行真实问答。已选择的模型是 ${modelLabel}；真实检索问答将在 MVP2 接入。`
                    : `This version does not run a real query yet. The selected model is ${modelLabel}; grounded query will be connected in MVP2.`}
                </p>
              </div>
            </article>
          ) : (
            <div className="ask-empty">
              <Sparkles aria-hidden="true" />
              <p>{t("askEmpty")}</p>
            </div>
          )}
        </div>
        <form className="ask-composer" onSubmit={submit}>
          <select
            aria-label={t("questionScope")}
            value={scope}
            onChange={(event) => setScope(event.target.value)}
          >
            <option value="current">{t("currentPage")}</option>
            <option value="local">{t("localGraph")}</option>
            <option value="workspace">{t("entireVault")}</option>
          </select>
          <label htmlFor="question-input" className="sr-only">
            {t("askPlaceholder")}
          </label>
          <input
            id="question-input"
            value={question}
            onChange={(event) => {
              setQuestion(event.target.value);
              setAnswered(false);
            }}
            placeholder={t("askPlaceholder")}
          />
          {question && (
            <button
              className="clear-question"
              type="button"
              aria-label={t("clearQuestion")}
              title={t("clearQuestion")}
              onClick={() => {
                setQuestion("");
                setAnswered(false);
              }}
            >
              <X />
            </button>
          )}
          <button
            className="send-question"
            type="submit"
            aria-label={t("ask")}
            title={t("ask")}
            disabled={!question.trim()}
          >
            <Send />
          </button>
        </form>
      </div>
    </section>
  );
}
