# MVP 1 本地演示

## 启动

```bash
cp .env.example .env
docker compose up --build -d
```

打开 <http://localhost:8000>。默认的 Mock LLM 不需要 API Key，适合稳定演示；需要真实生成时，可在模型设置中创建并测试 Ollama 或 OpenAI-compatible Profile，再设为默认模型。

## 完整演示路径

1. 确认底部 Health 为 `ok`，默认模型为 `Mock LLM`。
2. 点击左侧上传按钮，选择 `tests/fixtures/aurora-a.md`。
3. 查看 Job 从 `queued`、`running` 进入 `completed`。
4. 在文件树中打开生成的 Source Summary、`Project Aurora` 和 `Lin`。
5. 在关系图中拖动节点，并点击节点跳转到对应 Wiki。
6. 打开 Index 和 Activity，确认页面与本次 Job 可追溯。
7. 点击左侧打包图标，选择 **Create Vault ZIP**。
8. 等待状态变为 `completed`，点击 **Download Vault ZIP**。
9. 解压 ZIP；其中包含类型目录、Frontmatter、aliases、`[[wikilink]]`、`index.md`、`log.md`、Raw 来源和 `export-manifest.json`，可以直接作为 Obsidian Vault 打开。

重复上传同一文件不会创建重复 Source/Job。关闭并重新打开导出窗口后，前端会恢复上次 Export Job；如果导出记录存在但产物丢失，后端会重新生成同一份快照。

## 验收

```bash
make verify-mvp1
```

该 Gate 不会忽略失败，覆盖后端 lint/测试、前端 lint/单测/构建、Mock Edge E2E 和真实 Compose Edge E2E。
