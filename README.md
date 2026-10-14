# AI 原生工程实践 · P3 授权边界测试 Agent（授权状态驱动路线）

本仓库保存本组的 P3 开题、实现、证据与交接材料。与配对组题目相同、路线不同：

| | 本组 | 配对组 |
| --- | --- | --- |
| 题目 | P3 授权边界测试 Agent | P3 授权边界测试 Agent |
| 路线 | **授权状态驱动**：静态授权快照 vs 动态授权源 | 调度策略对照：固定流程 vs 模型动态调度 |
| 变化量 | 授权来源 | 计划器 |

两组共用同一套检查编号、Fixture 语义和证据字段，以便逐项比对；实现代码各自独立。

## 快速运行

需要 Python 3.11+，在仓库根目录执行，无需安装依赖、模型密钥或网络：

```text
python -m compileall -q src scripts eval
python -m unittest discover -s eval -v
python scripts/run_demo.py --scenario good
python scripts/run_demo.py --scenario known-bad
python scripts/run_demo.py --scenario timeout
python scripts/compare_strategies.py --scenario good --after-attempt 2 --revoke-test T02
python scripts/run_service_scenario.py --deployment correct
python scripts/run_service_scenario.py --deployment overpermissive
```

最后两条会启动仓库自带的**本地教学文档服务**（真实 HTTP、真实鉴权），把六项检查
接成真实请求。详见 [本地服务说明](docs/local-service.md)。

## 核心区分

本路线有一个必须说清的区别：

- **身份状态**（A / anonymous / revoked_A）是测试数据，描述虚构身份持有什么凭据，
  由模拟器决定该检查期望的状态码。
- **授权范围**（`authorization.py`）是本组自己的测试许可，说明当前允许启动哪些注册检查。

两条路线只有授权来源不同：

| | 策略 S：静态授权快照 | 策略 T：动态授权源 |
| --- | --- | --- |
| 读取时机 | 运行开始时读一次 | 每次动作前读最新版本 |
| 运行中撤权 | 拒绝，范围不变 | 生效，下一次准入即被拦 |
| 版本号 | 始终为 1 | 每接受一个事件加 1 |
| 拒绝记录 | 保留在 `refused_events` | 记录在 `applied_events` |

控制器、执行器、证据格式、结论判定、预算完全相同，所以行为差异只能归因于授权来源。

## 目录

| 路径 | 内容 |
| --- | --- |
| `src/authz_agent/registry.py` | 与配对组共享的契约：目标、身份、资源、六项检查 |
| `src/authz_agent/authorization.py` | 授权来源：静态快照与动态事件源 |
| `src/authz_agent/controller.py` | 独立控制器，每次准入重新读取授权范围 |
| `src/authz_agent/executor.py` | 纯内存模拟器，无 URL、无 Shell |
| `src/authz_agent/reporting.py` | 三类结论状态 |
| `src/authz_agent/runner.py` | 编排、预算、撤权事件、证据落盘 |
| `src/doc_service/` | 被测目标：本地教学文档服务（真实鉴权） |
| `src/authz_agent/target.py` | 受限 HTTP 客户端，只有注册检查能发请求 |
| `lab/public-fixtures/` | Good / Known Bad / Timeout 公开 Fixture |
| `eval/` | 授权语义与运行行为的 unittest |
| `scripts/` | 演示与对照实验入口 |
| `evidence/` | 运行证据：每个 run 一个目录，含哈希 |
| `config/` | 服务的正确配置与故意误配的 Known Bad 配置 |
| `docs/` | 开题卡、规格、状态模型、验收矩阵、登记表答案 |

## 当前状态

- 已实现：共享契约、两种授权来源、独立控制器、六项模拟检查、三类结论、预算与停止、
  运行中撤权事件、原始证据落盘、对照实验入口、**本地教学文档服务与真实 HTTP 检查**。
- 已通过：23 项自动测试；静态与动态两组对照实验；真实服务在正确配置下六项未确认、
  在误配配置下仅确认 `T02`。
- 未实现：模型相关能力（属配对组路线）、评价 Agent 后端、教师保留测试、
  伙伴独立复现与人工签署。

## 边界

1. 不执行任意 Shell、任意 URL；只接受注册的检查 ID。
2. 未注册目标或动作不执行，也不写进报告当安全。
3. 证据不足、被拒绝、未执行一律不得表述为"没有问题"。
4. 不承诺瞬时取消在途动作，只记录边界并如实说明未覆盖。
5. 模拟结果不冒充真实服务验收，AI 产出不替代本人实现、验证与签署。
6. 被测服务只在 `127.0.0.1` 监听；Agent 客户端不接受任意 URL 或未注册检查。

