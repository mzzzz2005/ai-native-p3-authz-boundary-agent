# 验收矩阵

| ID | 需求 | 验证 | 证据 |
| --- | --- | --- | --- |
| A01 | 未注册目标或动作不执行 | `test_unregistered_target_never_executes`、`test_unregistered_action_never_executes` | `report.json`、`events.jsonl` |
| A02 | Good 场景六项全覆盖 | `test_good_run_executes_all_six_checks` | Good 运行报告 |
| A03 | Known Bad 有证据地确认 | `test_known_bad_confirms_with_resolvable_evidence` | 报告引用 + 原始观察 |
| A04 | 工具错误判证据不足 | `test_timeout_is_inconclusive_and_reports_full_uncovered` | Timeout 报告 |
| A05 | 静态快照拒绝运行中撤权 | `test_static_snapshot_refuses_mid_run_withdrawal` | `refused_events` |
| A06 | 动态源在下次准入前生效 | `test_dynamic_source_stops_the_withdrawn_check` | `applied_events`、`denied` |
| A07 | 被撤权的检查不得报安全 | `test_withdrawn_check_never_reported_as_safe` | 该行结论 + 未覆盖列表 |
| A08 | 授权事件版本必须递增 | `test_dynamic_source_rejects_non_sequential_versions` | 异常 |
| A09 | 预算不可超出策略上限 | `test_budget_cannot_be_increased_beyond_policy` | 异常 |
| A10 | 证据哈希一致 | 各测试内的 checksums 校验 | `checksums.json` |
| A11 | 对照实验可复现 | `scripts/compare_strategies.py` | `evidence/experiment/experiment.json` |
| A12 | 被测服务真实鉴权 | `test_correct_deployment_enforces_authentication_and_ownership` | `doc_service/` |
| A13 | 拒绝响应不泄露内容 | `test_forbidden_response_never_leaks_the_canary` | 真实 403 响应 |
| A14 | 能发现真实误配且只发现它 | `test_overpermissive_deployment_confirms_only_the_real_defect` | `evidence/service/overpermissive/` |
| A15 | 凭据可在运行中真实撤销 | `test_revoked_credential_can_be_withdrawn_while_running` | 服务端 401 |
| A16 | 客户端拒绝任意 URL 与未注册检查 | `test_agent_refuses_arbitrary_url_and_unregistered_check` | 异常 |
| A17 | 传输失败判证据不足，不算发现 | `test_transport_failure_is_inconclusive_not_a_finding` | `tool_error` |

## 尚未验收

| 项目 | 状态 |
| --- | --- |
| 评价 Agent 与交叉评价 | 未开始，需冻结契约与配对组配合 |
| 伙伴独立复现 | 未开始 |
| 人工签署 | `human_signoff` 保持 `pending` |

自动测试通过不等于伙伴复核，也不等于教师验收。

