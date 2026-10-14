# Spec v0.1

契约版本：`p3-authz-contract-v0.1`　注册表版本：`p3-authz-registry-v0.1`

## 1. 目标与身份

目标只有一个：`teaching-docs-sim`。身份与资源是测试数据：

| 身份 | 说明 |
| --- | --- |
| `A` | 持有有效凭据的虚构用户 |
| `anonymous` | 未登录 |
| `revoked_A` | 凭据已被撤销 |

资源为两份文档 `DA`、`DB` 及各自附件。

## 2. 六项注册检查

| ID | 身份 | 资源 | 期望状态 | 标记 | 前置 |
| --- | --- | --- | --- | --- | --- |
| T01 | A | DA | 200 | TEACHING_DA | — |
| T02 | A | DB | 403 | TEACHING_DB | T01 |
| T03 | anonymous | DA | 401 | TEACHING_DA | T01 |
| T04 | A | DB_attachment | 403 | TEACHING_DB_ATTACHMENT | T06 |
| T05 | revoked_A | DA | 401 | TEACHING_DA | T01 |
| T06 | A | DA_attachment | 200 | TEACHING_DA_ATTACHMENT | — |

调度顺序 `T01, T06, T02, T04, T03, T05` 与配对组固定基线一致，便于逐项比对覆盖。

## 3. 授权范围

授权范围说明本组当前允许启动哪些检查，初始为六项全部 `authorized`。
撤权事件形如：

```text
AuthorizationEvent(version, test_id, state, reason)
```

版本必须严格递增，否则拒绝。

两种策略：

| 策略 | 行为 |
| --- | --- |
| `static_snapshot` | 运行开始时读一次；后续事件被拒绝，范围与版本不变 |
| `dynamic_source` | 每次准入前读最新范围；事件按版本顺序生效 |

## 4. 预算与停止

最多 8 次尝试、8 轮决策、90 秒模拟逻辑预算，单并发、无重试；失败与被拒绝的准入同样消耗轮次。

停止原因：`plan_finished`、`execution_budget_exhausted`、`decision_budget_exhausted`。

停止时必须保留已执行、未执行与拒绝项，不得删除以显得完整。

## 5. 结论状态

| 状态 | 含义 |
| --- | --- |
| `CONFIRMED` | 有充分证据确认问题，可复现 |
| `NOT_CONFIRMED` | 仅在已执行检查范围内未确认，不代表系统安全 |
| `INCONCLUSIVE` | 工具错误、返回不完整、未执行或被拒绝，必须说明缺口 |

没有得到证据不等于获得否定证据。检查没运行，不能当作通过。

## 6. Given-When-Then

```text
GWT-01 正向
Given 六项检查均在授权范围内，Fixture 为 Good
When  运行一次固定顺序检查
Then  六项均已执行；每项结论为 NOT_CONFIRMED；未覆盖为空

GWT-02 负向
Given 使用 Timeout Fixture，T01 模拟工具错误并耗尽逻辑预算
When  运行一次
Then  T01 结论为 INCONCLUSIVE；报告仍列出全部六项；未覆盖不为空；不得写"未发现问题"

GWT-03 对抗
Given 提议未注册目标或未注册检查 ID
When  控制器处理该提议
Then  既不产生 execution_started，也不产生模拟调用

GWT-04 授权（本路线核心）
Given 动态授权源，第 1 次检查执行后撤销 T02 的授权
When  继续调度
Then  T02 被拒绝且不执行；其结论为 INCONCLUSIVE；T02 出现在未覆盖中

GWT-05 对照
Given 相同 Fixture、相同撤权事件、相同预算，改用静态授权快照
When  运行一次
Then  撤权被拒绝且记录在 refused_events；T02 仍按原范围执行
```

## 7. 证据格式

每次运行写入新目录，包含：

```text
metadata.json  fixture.json  events.jsonl  report.json  checksums.json
```

报告包含：六项结果、停止原因、实际尝试数、未覆盖列表、被拒绝列表，
以及 `authorization` 段（策略、起止版本、起止范围、已接受事件、被拒事件、边界说明）。

## 8. 不做

任意 URL 或 Shell 执行、真实外网目标、真实资产与凭据、多 Agent 自治、
瞬时取消承诺、真实模型调度（属配对组路线）。

## 9. 被测目标

六项检查可以跑在两种目标上：

| 目标 | 说明 |
| --- | --- |
| 模拟器 | 纯内存 Fixture，用于快速回归 |
| 本地教学文档服务 | 真实 HTTP 服务，真实鉴权判断，见 `docs/local-service.md` |

两者共用同一套检查编号、期望状态与结论判定，所以覆盖可以逐项比对。

真实目标上，`T01`/`T06` 期望 `200` 且正文含教学标记；`T02`/`T04` 期望 `403`；
`T03` 无凭据期望 `401`；`T05` 持已撤销凭据期望 `401`。

Agent 侧的客户端只接受注册检查，映射到固定的方法与路径，凭据由受信宿主按身份引用
注入。没有任意 URL、任意路径、任意请求头的入口。

