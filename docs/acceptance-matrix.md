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

## 尚未验收

| 项目 | 状态 |
| --- | --- |
| 真实本地服务接入 | 未开始，需教师授权目标与环境 |
| 评价 Agent 与交叉评价 | 未开始，需冻结契约与配对组配合 |
| 伙伴独立复现 | 未开始 |
| 人工签署 | `human_signoff` 保持 `pending` |

自动测试通过不等于伙伴复核，也不等于教师验收。

