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
import type {
  ModelProfile,
  ModelProfileInput,
} from "../mvp1/contracts";

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  profiles?: ModelProfile[];
  defaultProfileId?: string;
  onCreateProfile?: (input: ModelProfileInput) => Promise<ModelProfile>;
  onTestProfile?: (profileId: string) => Promise<ModelProfile>;
  onSetDefaultProfile?: (profileId: string) => Promise<void>;
}

export function SettingsDialog({
  open,
  onClose,
  profiles = [],
  defaultProfileId = "",
  onCreateProfile,
  onTestProfile,
  onSetDefaultProfile,
}: SettingsDialogProps) {
  const [provider, setProvider] = useState<"ollama" | "openai">("ollama");
  const [apiKey, setApiKey] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [ollamaName, setOllamaName] = useState(modelProfileFixture.name);
  const [ollamaModel, setOllamaModel] = useState(modelProfileFixture.modelId);
  const [profileName, setProfileName] = useState("Remote API");
  const [modelName, setModelName] = useState("model-name");
  const [baseUrl, setBaseUrl] = useState("https://api.example.com/v1");
  const [externalTransferConfirmed, setExternalTransferConfirmed] =
    useState(false);

  if (!open) return null;

  const saveKey = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!apiKey.trim()) return;
    const credential = apiKey;
    setKeyConfigured(true);
    setApiKey("");
    if (onCreateProfile) {
      if (!externalTransferConfirmed) {
        setMessage("Credential staged. Confirm external data transfer to create the profile.");
        return;
      }
      try {
        const profile = await onCreateProfile({
          displayName: profileName,
          provider: "openai_compatible",
          baseUrl,
          modelName,
          apiKey: credential,
          externalTransferConfirmed,
        });
        setMessage(`${profile.displayName} was created. Test it before setting it as default.`);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Profile creation failed.");
        return;
      }
    }
  };

  const testProfile = async (profileId: string) => {
    if (!onTestProfile) return;
    try {
      const profile = await onTestProfile(profileId);
      setMessage(
        profile.status === "active"
          ? `${profile.displayName} connected in ${profile.latencyMs} ms.`
          : `${profile.displayName} is ${profile.status}.`,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Connection test failed.");
    }
  };

  const setDefaultProfile = async (profileId: string) => {
    if (!onSetDefaultProfile) return;
    try {
      await onSetDefaultProfile(profileId);
      setMessage("Workspace default model updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Default model update failed.");
    }
  };

  const createOllamaProfile = async () => {
    if (!onCreateProfile) {
      setMessage("Local Ollama profile is ready.");
      return;
    }
    try {
      const profile = await onCreateProfile({
        displayName: ollamaName,
        provider: "ollama",
        baseUrl: "",
        modelName: ollamaModel,
        externalTransferConfirmed: true,
      });
      setMessage(`${profile.displayName} was created. Test it before setting it as default.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Profile creation failed.");
    }
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
            {profiles.length > 0 && (
              <div className="model-profile-list" data-testid="model-profile-list">
                {profiles.map((profile) => (
                  <article key={profile.id} data-testid={`model-profile-${profile.id}`}>
                    <span>
                      <strong>{profile.displayName}</strong>
                      <small>
                        {profile.modelName} · {profile.status}
                        {profile.latencyMs !== null ? ` · ${profile.latencyMs} ms` : ""}
                        {profile.capabilities.streaming ? " · streaming" : ""}
                        {profile.capabilities.structuredOutput
                          ? " · structured output"
                          : ""}
                      </small>
                    </span>
                    <div>
                      <button
                        type="button"
                        onClick={() => void testProfile(profile.id)}
                      >
                        Test
                      </button>
                      <button
                        className="mod-cta"
                        type="button"
                        disabled={
                          profile.status !== "active" ||
                          profile.id === defaultProfileId
                        }
                        onClick={() => void setDefaultProfile(profile.id)}
                      >
                        {profile.id === defaultProfileId ? "Default" : "Set default"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
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
                  <input
                    value={ollamaName}
                    onChange={(event) => setOllamaName(event.target.value)}
                  />
                </label>
                <label>
                  <span>Model ID</span>
                  <input
                    value={ollamaModel}
                    onChange={(event) => setOllamaModel(event.target.value)}
                  />
                </label>
                <label>
                  <span>Server endpoint</span>
                  <input value="Server preset" readOnly />
                </label>
                <div className="settings-row">
                  <span>
                    Create profile
                    <small>Add this server-managed Ollama model to the vault.</small>
                  </span>
                  <button
                    className="mod-cta"
                    type="button"
                    onClick={() => void createOllamaProfile()}
                  >
                    Create
                  </button>
                </div>
              </div>
            ) : (
              <form className="settings-fields" onSubmit={saveKey}>
                <label>
                  <span>Profile name</span>
                  <input
                    value={profileName}
                    onChange={(event) => setProfileName(event.target.value)}
                  />
                </label>
                <label>
                  <span>Base URL</span>
                  <input
                    value={baseUrl}
                    onChange={(event) => setBaseUrl(event.target.value)}
                    placeholder="https://api.example.com/v1"
                  />
                </label>
                <label>
                  <span>Model ID</span>
                  <input
                    value={modelName}
                    onChange={(event) => setModelName(event.target.value)}
                    placeholder="model-name"
                  />
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
                {onCreateProfile && (
                  <label className="external-transfer-confirmation">
                    <input
                      type="checkbox"
                      checked={externalTransferConfirmed}
                      onChange={(event) =>
                        setExternalTransferConfirmed(event.target.checked)
                      }
                    />
                    <span>
                      I understand source content may be sent to this external endpoint.
                    </span>
                  </label>
                )}
                <button className="mod-cta save-key" type="submit" disabled={!apiKey.trim()}>
                  <Check />
                  {onCreateProfile
                    ? "Save credential and create profile"
                    : "Save credential"}
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
