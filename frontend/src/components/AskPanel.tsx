import {
  Bot,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minimize2,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { useState } from "react";

const mockAnswer =
  "当前资料显示：Project Aurora 于 2025-03-01 启动，负责人是 Lin。";

interface AskPanelProps {
  open: boolean;
  onToggle: () => void;
  maximized: boolean;
  onToggleMaximize: () => void;
}

export function AskPanel({
  open,
  onToggle,
  maximized,
  onToggleMaximize,
}: AskPanelProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [scope, setScope] = useState("current");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    setAnswer(mockAnswer);
  };

  return (
    <section
      className={`ask-panel${open ? " is-open" : ""}${maximized ? " is-maximized" : ""}`}
      data-testid="query-panel"
      aria-label="Ask local wiki"
    >
      <div className="ask-handle">
        <button className="ask-toggle" type="button" onClick={onToggle}>
          <Sparkles aria-hidden="true" />
          <span>Ask local wiki</span>
          <small>Local Ollama · offline · Mock mode</small>
          {open ? <ChevronDown /> : <ChevronUp />}
        </button>
        {open && (
          <button
            className="ask-maximize"
            type="button"
            aria-label={maximized ? "退出问答最大化" : "最大化问答"}
            onClick={onToggleMaximize}
          >
            {maximized ? <Minimize2 /> : <Maximize2 />}
          </button>
        )}
      </div>

      {open && (
        <div className="ask-body">
          <div className="ask-thread" aria-live="polite">
            {answer ? (
              <article className="answer-message" data-testid="mock-answer">
                <div className="assistant-avatar">
                  <Bot aria-hidden="true" />
                </div>
                <div>
                  <span className="answer-label">Mock answer</span>
                  <p>{answer}</p>
                  <button type="button" className="citation-pill">
                    [1] aurora-a.md · line 1
                  </button>
                  <button type="button" className="save-answer">
                    Save to Wiki
                  </button>
                </div>
              </article>
            ) : (
              <div className="ask-empty">
                <Sparkles aria-hidden="true" />
                <p>Ask a question grounded in this vault.</p>
              </div>
            )}
          </div>
          <form className="ask-composer" onSubmit={submit}>
            <select
              aria-label="问答范围"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
            >
              <option value="current">Current page</option>
              <option value="local">Local graph</option>
              <option value="workspace">Entire vault</option>
            </select>
            <label htmlFor="question-input" className="sr-only">
              输入问题
            </label>
            <input
              id="question-input"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about this knowledge space..."
            />
            {question && (
              <button
                className="clear-question"
                type="button"
                aria-label="清空问题"
                onClick={() => setQuestion("")}
              >
                <X />
              </button>
            )}
            <button
              className="send-question"
              type="submit"
              aria-label="Ask"
              disabled={!question.trim()}
            >
              <Send />
            </button>
          </form>
        </div>
      )}
    </section>
  );
}
