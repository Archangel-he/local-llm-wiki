import {
  Bot,
  Check,
  Database,
  FileCog,
  Info,
  Monitor,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useState } from "react";
import { modelProfileFixture } from "../fixtures/workspace";

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsDialog({ open, onClose }: SettingsDialogProps) {
  const [provider, setProvider] = useState<"ollama" | "openai">("ollama");
  const [apiKey, setApiKey] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (!open) return null;

  const saveKey = (event: React.FormEvent) => {
    event.preventDefault();
    if (!apiKey.trim()) return;
    setKeyConfigured(true);
    setApiKey("");
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="settings-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        data-testid="model-settings"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <aside className="settings-nav">
          <div className="settings-search">
            <Search aria-hidden="true" />
            <input aria-label="搜索设置" placeholder="Search settings..." />
          </div>
          <span className="settings-nav-label">Options</span>
          <button type="button">
            <FileCog />
            Files and links
          </button>
          <button type="button">
            <Monitor />
            Appearance
          </button>
          <button type="button">
            <SlidersHorizontal />
            Editor
          </button>
          <span className="settings-nav-label">Community plugins</span>
          <button className="is-active" type="button">
            <Bot />
            Local LLM
          </button>
          <button type="button">
            <Database />
            Storage
          </button>
          <button type="button">
            <Info />
            About
          </button>
        </aside>

        <div className="settings-content">
          <header>
            <div>
              <span>Plugin options</span>
              <h2 id="settings-title">Local LLM</h2>
            </div>
            <button type="button" aria-label="关闭设置" onClick={onClose}>
              <X />
            </button>
          </header>

          <section className="settings-section">
            <h3>Model profile</h3>
            <p>Choose the model provider used by this vault.</p>
            <div className="provider-tabs" role="tablist" aria-label="模型提供商">
              <button
                type="button"
                role="tab"
                aria-selected={provider === "ollama"}
                onClick={() => setProvider("ollama")}
              >
                Ollama
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={provider === "openai"}
                onClick={() => setProvider("openai")}
              >
                OpenAI-compatible API
              </button>
            </div>

            {provider === "ollama" ? (
              <div className="settings-fields">
                <label>
                  <span>Profile name</span>
                  <input defaultValue={modelProfileFixture.name} />
                </label>
                <label>
                  <span>Model ID</span>
                  <input defaultValue={modelProfileFixture.modelId} />
                </label>
                <label>
                  <span>Server endpoint</span>
                  <input value="Server preset" readOnly />
                </label>
                <div className="settings-row">
                  <span>
                    Test connection
                    <small>The local model is currently unavailable.</small>
                  </span>
                  <button
                    className="mod-cta"
                    type="button"
                    onClick={() => setMessage("Connection unavailable · Ollama is offline")}
                  >
                    Test
                  </button>
                </div>
                <div className="settings-row">
                  <span>
                    Workspace default
                    <small>Use this profile for queries in the current vault.</small>
                  </span>
                  <button
                    className="mod-cta"
                    type="button"
                    onClick={() => setMessage("Local Ollama is the workspace default")}
                  >
                    Set as default
                  </button>
                </div>
              </div>
            ) : (
              <form className="settings-fields" onSubmit={saveKey}>
                <label>
                  <span>Base URL</span>
                  <input placeholder="https://api.example.com/v1" />
                </label>
                <label>
                  <span>Model ID</span>
                  <input placeholder="model-name" />
                </label>
                <label>
                  <span>API Key</span>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder={keyConfigured ? "Configured" : "Write only"}
                    autoComplete="new-password"
                    data-testid="api-key-input"
                  />
                </label>
                <p className="credential-state" data-testid="credential-state">
                  {keyConfigured
                    ? "API Key configured. The stored value cannot be read."
                    : "No API Key configured."}
                </p>
                <button className="mod-cta save-key" type="submit" disabled={!apiKey.trim()}>
                  <Check />
                  Save credential
                </button>
              </form>
            )}
            {message && <p className="settings-message" role="status">{message}</p>}
          </section>
        </div>
      </section>
    </div>
  );
}
