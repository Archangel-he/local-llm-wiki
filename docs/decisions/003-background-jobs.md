# ADR-003：Redis + RQ 后台任务

- 状态：Accepted for MVP
- 日期：2026-07-23

## 背景

Ingest、Query、Lint 和 Export 可能运行数秒至数分钟，不能占用 HTTP 请求 Worker。四人团队从零开发，需要比完整消息中间件更简单的方案。

## 决策

- Redis 保存队列，RQ 执行 Python Job；
- PostgreSQL `jobs` 表保存用户可见状态和长期审计；
- Job 最大尝试 3 次，配置超时和安全错误码；
- Ingest 使用稳定幂等键；
- Wiki 变更在单个短事务中提交；
- Redis 丢失后根据 PostgreSQL queued/retrying/stale 状态恢复。

## 后果

优点：

- 与 Python/FastAPI 集成直接；
- 支持超时、重试、唯一 Job 和失败记录；
- 本地和单机云部署简单。

代价：

- RQ 是 Python-only；
- Redis 不是强一致业务数据库；
- 需要自行实现 PostgreSQL 状态与 RQ 状态协调。

## 替换条件

出现复杂 DAG、多语言 Worker、严格消息交付或大规模路由需求时，再评估 Celery、Dramatiq、Temporal 或云队列。
