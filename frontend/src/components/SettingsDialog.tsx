import {
  Check,
  Cloud,
  Languages,
  LoaderCircle,
  Pencil,
  RefreshCw,
  Server,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useI18n } from "../i18n";
import type {
  ModelDiscoveryInput,
  ModelProfile,
  ModelProfileInput,
} from "../mvp1/contracts";

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  profiles?: ModelProfile[];
  defaultProfileId?: string;
  onCreateProfile?: (input: ModelProfileInput) => Promise<ModelProfile>;
  onUpdateProfile?: (
    profileId: string,
    input: ModelProfileInput,
  ) => Promise<ModelProfile>;
  onDeleteProfile?: (profileId: string) => Promise<void>;
  onDiscoverModels?: (input: ModelDiscoveryInput) => Promise<string[]>;
  onTestProfile?: (profileId: string) => Promise<ModelProfile>;
  onSetDefaultProfile?: (profileId: string) => Promise<void>;
}

type ProviderPreset = {
  id: string;
  label: string;
  provider: ModelProfileInput["provider"];
  baseUrl: string;
  profileName: string;
  requiresKey: boolean;
};

const providerPresets: ProviderPreset[] = [
  {
    id: "deepseek",
    label: "DeepSeek",
    provider: "openai_compatible",
    baseUrl: "https://api.deepseek.com",
    profileName: "DeepSeek",
    requiresKey: true,
  },
  {
    id: "openai",
    label: "OpenAI",
    provider: "openai_compatible",
    baseUrl: "https://api.openai.com",
    profileName: "OpenAI",
    requiresKey: true,
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    provider: "openai_compatible",
    baseUrl: "https://openrouter.ai/api",
    profileName: "OpenRouter",
    requiresKey: true,
  },
  {
    id: "siliconflow",
    label: "SiliconFlow",
    provider: "openai_compatible",
    baseUrl: "https://api.siliconflow.cn",
    profileName: "SiliconFlow",
    requiresKey: true,
  },
  {
    id: "dashscope",
    label: "Qwen / DashScope",
    provider: "openai_compatible",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode",
    profileName: "Qwen",
    requiresKey: true,
  },
  {
    id: "ollama",
    label: "Ollama",
    provider: "ollama",
    baseUrl: "http://host.docker.internal:11434",
    profileName: "Local Ollama",
    requiresKey: false,
  },
  {
    id: "custom",
    label: "Custom",
    provider: "openai_compatible",
    baseUrl: "",
    profileName: "Custom API",
    requiresKey: true,
  },
];

function presetForProfile(profile: ModelProfile) {
  if (profile.provider === "ollama") {
    return providerPresets.find((preset) => preset.id === "ollama")!;
  }
  return (
    providerPresets.find((preset) => {
      if (!preset.baseUrl || preset.provider !== profile.provider) return false;
      return new URL(preset.baseUrl).origin === profile.endpointOrigin;
    }) ?? providerPresets.find((preset) => preset.id === "custom")!
  );
}

function providerErrorMessage(error: unknown, language: "zh" | "en") {
  const fallback =
    language === "zh"
      ? "无法读取模型，请检查 API 地址和密钥。"
      : "Could not load models. Check the API URL and key.";
  if (!(error instanceof Error)) return fallback;
  if (language !== "zh") return error.message || fallback;

  const translations: Record<string, string> = {
    "The provider rejected this API key.": "API Key 被服务商拒绝，请更换有效密钥。",
    "The provider URL is blocked by server policy.":
      "该 API 地址被服务器安全策略拦截。",
    "The provider rate limit was reached. Try again shortly.":
      "已达到服务商请求频率限制，请稍后重试。",
    "The provider did not respond in time.": "服务商响应超时，请稍后重试。",
    "The provider returned an unsupported model list.":
      "服务商返回了无法识别的模型列表。",
    "The provider is currently unavailable.": "服务商当前不可用，请稍后重试。",
  };
  return translations[error.message] ?? error.message ?? fallback;
}

export function SettingsDialog({
  open,
  onClose,
  profiles = [],
  defaultProfileId = "",
  onCreateProfile,
  onUpdateProfile,
  onDeleteProfile,
  onDiscoverModels,
  onTestProfile,
  onSetDefaultProfile,
}: SettingsDialogProps) {
  const { language, setLanguage, t } = useI18n();
  const initialPreset = providerPresets[0];
  const [presetId, setPresetId] = useState(initialPreset.id);
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [profileName, setProfileName] = useState(initialPreset.profileName);
  const [baseUrl, setBaseUrl] = useState(initialPreset.baseUrl);
  const [modelName, setModelName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [externalTransferConfirmed, setExternalTransferConfirmed] =
    useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingProfileId, setTestingProfileId] = useState<string | null>(null);
  const [deletingProfileId, setDeletingProfileId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const preset =
    providerPresets.find((candidate) => candidate.id === presetId) ??
    initialPreset;
  const editingProfile = profiles.find(
    (profile) => profile.id === editingProfileId,
  );

  const statusText = useMemo(
    () => ({
      untested: language === "zh" ? "尚未测试" : "Not tested",
      active: language === "zh" ? "可用" : "Ready",
      invalid: language === "zh" ? "配置无效" : "Invalid",
      unavailable: language === "zh" ? "不可用" : "Unavailable",
    }),
    [language],
  );

  if (!open) return null;

  const selectPreset = (nextPreset: ProviderPreset) => {
    setPresetId(nextPreset.id);
    setEditingProfileId(null);
    setProfileName(nextPreset.profileName);
    setBaseUrl(nextPreset.baseUrl);
    setModelName("");
    setApiKey("");
    setKeyConfigured(false);
    setExternalTransferConfirmed(nextPreset.provider === "ollama");
    setAvailableModels([]);
    setMessage(null);
  };

  const editProfile = (profile: ModelProfile) => {
    const profilePreset = presetForProfile(profile);
    setPresetId(profilePreset.id);
    setEditingProfileId(profile.id);
    setProfileName(profile.displayName);
    setBaseUrl(
      profilePreset.id === "custom"
        ? profile.endpointOrigin
        : profilePreset.baseUrl,
    );
    setModelName(profile.modelName);
    setApiKey("");
    setKeyConfigured(profile.hasCredential);
    setExternalTransferConfirmed(profile.provider === "ollama" || profile.hasCredential);
    setAvailableModels([]);
    setMessage(null);
  };

  const discoverModels = async () => {
    if (!baseUrl.trim()) {
      setMessage(
        language === "zh" ? "请先填写 API 地址。" : "Enter the API URL first.",
      );
      return;
    }
    if (preset.requiresKey && !apiKey.trim() && !keyConfigured) {
      setMessage(
        language === "zh"
          ? "请输入 API Key 后再读取模型。"
          : "Enter an API key before loading models.",
      );
      return;
    }

    setDiscovering(true);
    setMessage(null);
    try {
      const models = onDiscoverModels
        ? await onDiscoverModels({
            profileId: editingProfileId ?? undefined,
            provider: preset.provider,
            baseUrl: baseUrl.trim(),
            apiKey: apiKey.trim() || undefined,
          })
        : [modelName || "model-name"];
      setAvailableModels(models);
      if (!models.includes(modelName)) setModelName(models[0] ?? "");
      setMessage(
        models.length > 0
          ? language === "zh"
            ? `已从服务商读取 ${models.length} 个模型。`
            : `Loaded ${models.length} models from the provider.`
          : language === "zh"
            ? "服务商没有返回可用模型。"
            : "The provider returned no available models.",
      );
    } catch (error) {
      setMessage(providerErrorMessage(error, language));
    } finally {
      setDiscovering(false);
    }
  };

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!modelName.trim()) {
      setMessage(
        language === "zh"
          ? "请先读取并选择一个模型。"
          : "Load and select a model first.",
      );
      return;
    }
    if (preset.requiresKey && !apiKey.trim() && !keyConfigured) {
      setMessage(
        language === "zh" ? "请输入 API Key。" : "Enter an API key.",
      );
      return;
    }
    if (
      preset.provider === "openai_compatible" &&
      !externalTransferConfirmed
    ) {
      setMessage(
        language === "zh"
          ? "请确认允许将资料发送到该外部服务。"
          : "Confirm external data transfer before saving.",
      );
      return;
    }

    const input: ModelProfileInput = {
      displayName: profileName.trim(),
      provider: preset.provider,
      baseUrl: baseUrl.trim(),
      modelName: modelName.trim(),
      apiKey: apiKey.trim() || undefined,
      externalTransferConfirmed:
        preset.provider === "ollama" || externalTransferConfirmed,
    };
    const sameNameProfile = profiles.find(
      (profile) =>
        profile.provider !== "mock" &&
        profile.displayName.trim().toLocaleLowerCase() ===
          input.displayName.toLocaleLowerCase(),
    );
    const targetProfileId = editingProfileId ?? sameNameProfile?.id ?? null;

    setSaving(true);
    setMessage(null);
    try {
      let profile: ModelProfile;
      if (targetProfileId && onUpdateProfile) {
        profile = await onUpdateProfile(targetProfileId, input);
      } else if (onCreateProfile) {
        profile = await onCreateProfile(input);
      } else {
        profile = {
          id: targetProfileId ?? "local-preview",
          displayName: input.displayName,
          provider: input.provider,
          endpointOrigin: input.baseUrl,
          modelName: input.modelName,
          hasCredential: Boolean(input.apiKey),
          status: "untested",
          lastTestedAt: null,
          latencyMs: null,
          capabilities: { streaming: false, structuredOutput: false },
        };
      }
      setEditingProfileId(profile.id);
      setKeyConfigured(profile.hasCredential || Boolean(input.apiKey));
      setApiKey("");
      setMessage(
        language === "zh"
          ? "配置已保存。请测试连接，通过后即可设为默认模型。"
          : "Configuration saved. Test it before making it the default.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : language === "zh"
            ? "配置保存失败。"
            : "Configuration could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  };

  const testProfile = async (profileId: string) => {
    if (!onTestProfile) return;
    const profileName =
      profiles.find((profile) => profile.id === profileId)?.displayName ?? "";
    setTestingProfileId(profileId);
    setMessage(
      language === "zh"
        ? `正在测试 ${profileName}，请稍候…`
        : `Testing ${profileName}. Please wait…`,
    );
    try {
      const profile = await onTestProfile(profileId);
      setMessage(
        language === "zh"
          ? `${profile.displayName} 连接成功（${profile.latencyMs ?? 0} ms），可以设为默认模型。`
          : `${profile.displayName} is ready (${profile.latencyMs ?? 0} ms) and can now be set as default.`,
      );
    } catch (error) {
      const reason = error instanceof Error ? error.message : "";
      const reasonText =
        reason === "invalid_response"
          ? language === "zh"
            ? "服务商返回格式不兼容。请刷新页面后重试。"
            : "The provider returned an incompatible response. Refresh and try again."
          : reason;
      setMessage(
        reasonText === "model_not_found"
          ? language === "zh"
            ? "服务可访问，但模型 ID 不存在。请重新读取模型列表并选择。"
            : "The service is reachable, but that model ID does not exist. Reload the model list."
          : reasonText ||
              (language === "zh"
                ? "连接测试失败，请检查地址、密钥和模型。"
                : "Connection test failed. Check the URL, key and model."),
      );
    } finally {
      setTestingProfileId(null);
    }
  };

  const deleteProfile = async (profile: ModelProfile) => {
    if (!onDeleteProfile) return;
    const confirmed = window.confirm(
      language === "zh"
        ? `确定删除“${profile.displayName}”吗？保存的 API Key 也会被清除。`
        : `Delete “${profile.displayName}”? Its saved API key will also be removed.`,
    );
    if (!confirmed) return;

    setDeletingProfileId(profile.id);
    setMessage(
      language === "zh"
        ? `正在删除 ${profile.displayName}…`
        : `Deleting ${profile.displayName}…`,
    );
    try {
      await onDeleteProfile(profile.id);
      if (editingProfileId === profile.id) selectPreset(initialPreset);
      setMessage(
        language === "zh"
          ? `${profile.displayName} 已删除。`
          : `${profile.displayName} was deleted.`,
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : language === "zh"
            ? "配置删除失败。"
            : "The configuration could not be deleted.",
      );
    } finally {
      setDeletingProfileId(null);
    }
  };

  const setDefaultProfile = async (profileId: string) => {
    if (!onSetDefaultProfile) return;
    try {
      await onSetDefaultProfile(profileId);
      setMessage(
        language === "zh"
          ? "默认模型已切换。"
          : "The default model has been updated.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : language === "zh"
            ? "默认模型切换失败。"
            : "The default model could not be updated.",
      );
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="settings-modal is-focused"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        data-testid="model-settings"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="settings-content">
          <header>
            <h2 id="settings-title">{t("settings")}</h2>
            <button
              type="button"
              aria-label={t("closeSettings")}
              title={t("closeSettings")}
              onClick={onClose}
            >
              <X />
            </button>
          </header>

          <section className="settings-section interface-settings">
            <div className="settings-section-heading">
              <Languages aria-hidden="true" />
              <div>
                <h3>{t("interface")}</h3>
                <p>{t("languageHelp")}</p>
              </div>
            </div>
            <label className="language-setting">
              <span>{t("language")}</span>
              <select
                value={language}
                onChange={(event) =>
                  setLanguage(event.target.value === "zh" ? "zh" : "en")
                }
                data-testid="language-select"
              >
                <option value="zh">{t("chinese")}</option>
                <option value="en">{t("english")}</option>
              </select>
            </label>
          </section>

          <section className="settings-section model-setup">
            <div className="settings-section-heading">
              <Cloud aria-hidden="true" />
              <div>
                <h3>{language === "zh" ? "模型服务" : "Model service"}</h3>
                <p>
                  {language === "zh"
                    ? "选择服务商，读取真实可用模型，再保存并测试。"
                    : "Choose a provider, load its real models, then save and test."}
                </p>
              </div>
            </div>

            {profiles.length > 0 && (
              <div className="model-profile-list" data-testid="model-profile-list">
                {profiles.map((profile) => (
                  <article
                    className={profile.id === defaultProfileId ? "is-default" : ""}
                    key={profile.id}
                    data-testid={`model-profile-${profile.id}`}
                  >
                    <span>
                      <strong>{profile.displayName}</strong>
                      <small>
                        {profile.modelName} · {profile.endpointOrigin}
                      </small>
                      <em className={`profile-status ${profile.status}`}>
                        {statusText[profile.status]}
                      </em>
                    </span>
                    <div>
                      {profile.provider !== "mock" && (
                        <>
                          <button
                            type="button"
                            disabled={deletingProfileId === profile.id}
                            onClick={() => editProfile(profile)}
                          >
                            <Pencil />
                            {language === "zh" ? "编辑" : "Edit"}
                          </button>
                          <button
                            className="mod-danger"
                            type="button"
                            disabled={deletingProfileId === profile.id}
                            onClick={() => void deleteProfile(profile)}
                          >
                            {deletingProfileId === profile.id ? (
                              <LoaderCircle className="is-spinning" />
                            ) : (
                              <Trash2 />
                            )}
                            {deletingProfileId === profile.id
                              ? language === "zh"
                                ? "删除中"
                                : "Deleting"
                              : language === "zh"
                                ? "删除"
                                : "Delete"}
                          </button>
                        </>
                      )}
                      <button
                        type="button"
                        disabled={
                          testingProfileId === profile.id ||
                          deletingProfileId === profile.id
                        }
                        onClick={() => void testProfile(profile.id)}
                      >
                        <RefreshCw
                          className={
                            testingProfileId === profile.id ? "is-spinning" : ""
                          }
                        />
                        {testingProfileId === profile.id
                          ? language === "zh"
                            ? "测试中"
                            : "Testing"
                          : language === "zh"
                            ? "测试连接"
                            : "Test"}
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
                        {profile.id === defaultProfileId
                          ? language === "zh"
                            ? "当前默认"
                            : "Default"
                          : language === "zh"
                            ? "使用此模型"
                            : "Use model"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}

            <div className="provider-heading">
              <strong>
                {editingProfile
                  ? language === "zh"
                    ? `正在编辑：${editingProfile.displayName}`
                    : `Editing: ${editingProfile.displayName}`
                  : language === "zh"
                    ? "添加模型服务"
                    : "Add a model service"}
              </strong>
              {editingProfile && (
                <button
                  type="button"
                  onClick={() => selectPreset(initialPreset)}
                >
                  {language === "zh" ? "新建配置" : "New configuration"}
                </button>
              )}
            </div>

            <div className="provider-presets" role="group" aria-label="Providers">
              {providerPresets.map((candidate) => (
                <button
                  type="button"
                  className={candidate.id === presetId ? "is-active" : ""}
                  aria-pressed={candidate.id === presetId}
                  key={candidate.id}
                  onClick={() => selectPreset(candidate)}
                >
                  {candidate.provider === "ollama" ? <Server /> : <Cloud />}
                  <span>{candidate.label}</span>
                </button>
              ))}
            </div>

            <form className="settings-fields api-setup-form" onSubmit={saveProfile}>
              <label>
                <span>{t("profileName")}</span>
                <input
                  value={profileName}
                  onChange={(event) => setProfileName(event.target.value)}
                  required
                />
              </label>
              <label>
                <span>{t("baseUrl")}</span>
                <input
                  value={baseUrl}
                  onChange={(event) => {
                    setBaseUrl(event.target.value);
                    setAvailableModels([]);
                  }}
                  placeholder="https://api.example.com"
                  required
                />
              </label>
              {preset.requiresKey && (
                <label>
                  <span>{t("apiKey")}</span>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder={
                      keyConfigured
                        ? language === "zh"
                          ? "已保存；留空表示继续使用"
                          : "Stored; leave blank to keep it"
                        : t("writeOnly")
                    }
                    autoComplete="new-password"
                    data-testid="api-key-input"
                  />
                </label>
              )}
              <div className="model-discovery-row">
                <button
                  className="load-models"
                  type="button"
                  disabled={discovering}
                  onClick={() => void discoverModels()}
                >
                  {discovering ? (
                    <LoaderCircle className="is-spinning" />
                  ) : (
                    <RefreshCw />
                  )}
                  {discovering
                    ? language === "zh"
                      ? "正在读取…"
                      : "Loading…"
                    : availableModels.length
                      ? language === "zh"
                        ? "刷新模型列表"
                        : "Refresh models"
                      : language === "zh"
                        ? "连接并读取模型"
                        : "Connect & load models"}
                </button>
                {availableModels.length > 0 && (
                  <span>
                    {language === "zh"
                      ? `${availableModels.length} 个可用模型`
                      : `${availableModels.length} models available`}
                  </span>
                )}
              </div>
              <label>
                <span>{t("modelId")}</span>
                {availableModels.length > 0 ? (
                  <select
                    value={modelName}
                    onChange={(event) => setModelName(event.target.value)}
                    required
                  >
                    {availableModels.map((model) => (
                      <option value={model} key={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={modelName}
                    onChange={(event) => setModelName(event.target.value)}
                    placeholder={
                      language === "zh"
                        ? "先读取模型，也可以手动填写模型 ID"
                        : "Load models or enter a model ID"
                    }
                    required
                  />
                )}
              </label>
              {preset.provider === "openai_compatible" && (
                <label className="external-transfer-confirmation">
                  <input
                    type="checkbox"
                    checked={externalTransferConfirmed}
                    onChange={(event) =>
                      setExternalTransferConfirmed(event.target.checked)
                    }
                  />
                  <span>{t("externalTransfer")}</span>
                </label>
              )}
              <p className="credential-state" data-testid="credential-state">
                {keyConfigured
                  ? language === "zh"
                    ? "密钥已安全保存；不会在界面中回显。"
                    : "The key is stored securely and is never displayed."
                  : language === "zh"
                    ? "密钥只会发送给你选择的模型服务。"
                    : "The key is sent only to the provider you select."}
              </p>
              <button
                className="mod-cta save-key"
                type="submit"
                disabled={saving}
              >
                {saving ? <LoaderCircle className="is-spinning" /> : <Check />}
                {editingProfile
                  ? language === "zh"
                    ? "更新配置"
                    : "Update configuration"
                  : language === "zh"
                    ? "保存配置"
                    : "Save configuration"}
              </button>
            </form>

            {message && (
              <p className="settings-message" role="status">
                {message}
              </p>
            )}
          </section>
        </div>
      </section>
    </div>
  );
}
