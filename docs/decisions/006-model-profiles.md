# ADR-006：Ollama 与自定义 API 使用 Model Profile

## 状态

Accepted

## 背景

项目默认在 Mac Studio 上使用 Ollama，但用户还需要使用自己配置的云端或自托管 API。简单地让浏览器保存 API Key 或让每个任务接受任意 URL，会带来密钥泄漏、SSRF、任务不可复现和团队费用归属不清等问题。

## 决策

- MVP 只支持 `ollama` 和 `openai_compatible` 两类 Provider；
- 用户通过 Model Profile 保存 provider、base URL、model ID 和凭据；
- API Key 只写入后端，使用数据库外的主密钥进行认证加密，之后不再返回明文；
- 个人 Profile 只用于所有者自己的 Query；
- 会更新共享 Wiki 的 Ingest、Lint、Query 保存和 Schema 任务使用 Workspace 默认 Profile；
- Workspace Profile 只能由 Owner 管理，成员只能看到脱敏元数据；
- Job 固化 `model_profile_id` 和非秘密模型快照，便于审计与重试；
- 自定义 Endpoint 必须通过协议、DNS/IP、重定向和出站策略检查；
- 浏览器不直接调用 Ollama 或外部模型 API。

## 结果

优点：

- 本地 Ollama 与 BYOK 共用统一任务流程；
- 成员私钥不会隐式共享；
- Wiki 写入使用稳定、可审计的 Workspace 策略；
- 后续可增加原生 Provider adapter，而不修改业务流程。

代价：

- 需要凭据加密、轮换和恢复设计；
- 需要防止自定义 URL 造成 SSRF；
- 不能承诺任意供应商协议都能直接使用；
- 外部 API 会把必要的来源片段发送到用户配置的服务。
- 云端服务器不能直接使用访问者 Mac 的 localhost Ollama，除非未来增加安全的 Local Connector。

## 替换条件

当 OpenAI-compatible 适配无法满足明确需求时，为相应供应商增加独立 adapter；不通过在通用配置中堆叠供应商特例解决。
