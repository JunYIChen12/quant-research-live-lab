# 20260918-006 1.0 已验收成果持久化与远程对齐

## 状态与责任

- 创建日期：2026-09-18，Asia/Shanghai。
- 状态：`IN_PROGRESS`。
- 当前责任线程：`20｜实施｜20260918-006`。
- 唯一根目录：`D:/CodexProjects/projects/quant-research-live-lab`。
- 本地基线：分支 `codex/workbench-init`，HEAD `ba8738fe18289398a8c6713772416facddb5532d`。
- 远程基线：`main` 为 `d524b1218746133410c409134749fe7058ddf3b2`。
- 实施基线：远程 `main` 与目标分支在 2026-09-18 启动复核时均为 `d524b1218746133410c409134749fe7058ddf3b2`；隔离工作树分支为 `codex/13-accepted-baseline-integration`。
- GitHub 正式任务：[Issue #13](https://github.com/JunYIChen12/quant-research-live-lab/issues/13)。
- 来源：已关闭任务 `20260912-002` 和 `20260917-005` 的独立验收结果。

## 单一目标

在完整保护现有未提交工作区的前提下，形成一套可执行、可回滚、可独立验收的最小方案，把已验收的 1.0 候选验证入口和单正式 Dry-run 监督闭环迁移到最新远程 `main`，并通过一个受治理 PR 持久化。

## 已确认事实

- 候选验证入口已经完成独立验收，证据保留在 `20260912-002`；验收不授权 Dry-run、实盘或盈利结论。
- 单正式 Dry-run 监督闭环已经完成第二次独立验收，证据保留在 `20260917-005`；未启动真实 Freqtrade。
- 上述代码、测试和任务证据仍位于未提交工作区；本地分支 HEAD 与 `origin/codex/workbench-init` 一致，但工作区不干净。
- 远程 `main` 已前进到 PR #12 的 merge commit，不能直接把旧本地 HEAD 当作当前集成基线。
- GitHub Issue #6 和 PR #7 仍开放。PR #7 未合并，且保留运行制品绑定、force-entry 实际金额限制和运行时风险闸门三个 P1 问题；项目任务记录已明确它不是当前实施基线。

## 分析范围

1. 固定两个已验收切片的准确文件清单、依赖关系和证据来源，区分用户既有修改、任务实现和控制塔状态文件。
2. 设计从最新 `main` 建立隔离集成基线并无损迁移当前成果的方法，原始工作区保持不变。
3. 判断一个整合 PR 是否足够；只有出现不可审查的独立变更边界时才拆分，不为整理历史制造额外平台或抽象。
4. 定义 PR 的允许文件、测试、CI、独立验收、失败停止和回滚标准。
5. 明确 Issue #6 / PR #7 与当前实现的替代关系；任何关闭、评论或状态修改必须在分析结论确认后执行。
6. 同步 README、项目状态和任务证据所需的最小文档范围，不重写历史记录。

## 不在范围

- 不在本任务分析阶段修改 `src/`、`tests/`、配置、策略、发布政策、安全模型或工作流。
- 不清理、暂存、提交、重置、移动或覆盖当前未提交修改。
- 不创建集成分支或 PR，不关闭 Issue #6 / PR #7，不修改 GitHub 标签或保护规则。
- 不安装依赖，不启动 Freqtrade、Web、后台服务或 Windows 自启，不连接交易所，不下载行情，不读取真实凭据。
- 不开展 Windows 宿主与通知、真实候选验证、正式 Dry-run 运行、1.1 候选并发或实盘适配。

## 事实、推断与建议

### 事实

- 当前已验收能力尚未进入远程 `main`，远程协作者和 CI 不能从正式分支复核这些成果。
- 当前工作区同时包含受验收任务产生的文件和更早的既有修改，不能把整个工作区直接提交为一个未经归属核对的变更。
- 旧 PR #7 基于更早的 `main`，其实现与当前监督闭环不同，且仍有未解决 P1。

### 推断

- 最低风险路径是在隔离工作树中从最新 `main` 建立集成分支，再按已核对文件清单迁移成果；不应在当前脏工作区执行 rebase、reset 或历史改写。
- 两个切片已经分别独立验收且共同构成 1.0 本地基线，默认优先一个整合 Issue/PR；只有文件归属或审查证据证明必须拆分时才改变方案。
- Issue #6 / PR #7 更适合作为被当前方案替代的历史记录，而不是继续修补并合并；该结论仍需在 READY 前形成可复核处置文本。

### 建议

- 下一步由控制塔继续只读分析文件归属、与 `main` 的差异和迁移顺序，形成 READY 契约。
- 达到 READY 后只创建一个实施线程；实施线程在隔离集成工作树中操作，原始工作区只作为只读来源。

## READY 条件

- 已列出每个拟迁移文件、来源任务、归属、目标路径和是否允许修改，未把未知或用户既有修改混入范围。
- 已确认最新 `main`、目标分支方式、单一 PR 边界和 GitHub Issue #13 的状态要求。
- 已形成 Issue #6 / PR #7 的准确处置方案，且不会把旧 P1 代码带入当前实现。
- 已定义实施白名单、禁止项、回滚方法和停止条件。
- 已定义定向测试、全量 pytest、Ruff、pip check、compileall、`git diff --check`、CI 和独立验收方法。
- 已明确 Playwright 缺失、真实 Freqtrade 未运行及其他未验证事项如何如实保留。
- 方案不修改安全/发布规则，不启动 Dry-run，不扩大资本、杠杆、持仓数、品种或亏损上限。

## READY 实施契约

### 集成基线与方式

- 实施前重新在线核对 `main`。当前已确认基线为 `d524b1218746133410c409134749fe7058ddf3b2`；若 `main` 已变化但未触及白名单文件，可记录新 SHA 后继续，若发生重叠则停止并交回控制塔。
- 从最新 `main` 创建隔离工作树和分支 `codex/13-accepted-baseline-integration`。原始 `D:/CodexProjects/projects/quant-research-live-lab` 工作区只读，不执行 rebase、reset、clean、stash、checkout、暂存或提交。
- 不迁移 `codex/workbench-init` 的提交历史；仅按白名单迁移当前最终文件内容。复制前记录来源文件 SHA-256，复制后逐项核对；语义合并文件和状态文件除外。
- 只创建一个关联 Issue #13 的 Draft PR。候选验证和监督闭环共同构成一个 1.0 基线，无事实支持拆分为多个 PR。

### 实施白名单

1. 直接迁移产品文件：`src/quant_lab/release.py`、`src/quant_lab/validation.py`、`src/quant_lab/dry_run.py`。
2. 直接迁移测试：`tests/test_release.py`、`tests/test_validation.py`、`tests/test_dry_run_supervisor.py`、`tests/fixtures/validation_cli/CliCandidate.py`、`tests/fixtures/validation_cli/freqtrade.json`、`tests/fixtures/validation_cli/risk.toml`。不得迁移 `__pycache__` 或其他生成物。
3. 直接迁移 `docs/codex/` 下现有 15 个 Markdown 文件；实施、验收和关闭时只按工作流更新当前任务状态相关内容。
4. 语义合并 `AGENTS.md`：保留远程 GitHub task governance 与本地 Codex Workflow 两节，不降低任何安全要求。
5. 语义合并 `CHANGELOG.md`：保留远程 2026-09-14/17 治理记录和本地 2026-09-12 工作台记录，并增加本次集成的最小记录。
6. 最小更新 `README.md`：只说明候选验证和监督/Web 基线已纳入代码、真实 Dry-run 尚未运行、Windows 宿主/通知尚未完成、未授权实盘或盈利结论。

### 禁止修改

- 不修改 `.github/**`、`tools/governance.py`、`tests/test_governance.py`、`docs/governance/**`、`docs/safety-model.md`、`docs/repository-settings.md`、`CONTRIBUTING.md`、`SECURITY.md`。
- 不修改 `pyproject.toml`、`src/quant_lab/__init__.py`、`src/quant_lab/gates.py`、`tests/test_gates.py`、示例风险/发布配置、策略、交易适配器、资本/杠杆/持仓/品种/亏损限制。
- 不提交运行数据库、日志、验证输出、发布制品、缓存、虚拟环境、凭据或账户数据。

### 旧 Issue / PR 处置

- 不复用或修补 PR #7 的实现，也不删除其分支或历史。
- 新 Draft PR 建立并可复核后，在 Issue #6 和 PR #7 留下被 Issue #13 / 新 PR 替代的精确说明，再将 PR #7 关闭为未合并、Issue #6 关闭为 `not_planned`；若新 PR 尚未建立或治理检查失败，则保持两者开放。

### 验证与验收

- 定向执行候选验证、发布、监督和治理测试：`test_validation.py`、`test_release.py`、`test_dry_run_supervisor.py`、`test_governance.py`。
- 执行全量 pytest、Ruff、`pip check`、`compileall` 和 `git diff --check`。
- 使用现有 Freqtrade 2026.8 环境执行合成策略 `list-strategies`，并执行候选验证“缺少可执行文件”失败关闭检查；不启动 Dry-run，不连接交易所，不下载行情。
- 对 Web 执行本机回环 HTTP/DOM 检查；Playwright 可用时补视觉检查，不可用时如实记录跳过。
- 检查 PR diff 仅包含白名单、无生成物或敏感信息；远程 CI 的 `test` 和 `governance` 均须达到治理要求。
- 实施完成后状态为 `READY_FOR_VERIFY`，由独立验收线程复核准确 PR HEAD；验收线程不自行修复。

### 停止与回滚

- `main` 与白名单发生重叠、来源 hash 在迁移期间变化、文件归属不清、需要越界修改、测试/CI/治理失败、出现凭据或真实账户数据时立即停止，记录 `BLOCKED` 或 `REWORK`。
- 合并前回滚为关闭 PR 并删除隔离分支/工作树，原始工作区不变；合并后只能通过新的受治理 revert PR 回退，不移动或删除发布标签。

## 当前验证与限制

- 启动前核对 cwd、分支、HEAD、远程、工作区状态、任务索引、当前指针和相关任务文件；没有执行产品测试，因为本轮仅登记分析任务。
- GitHub Issue #13 创建后依次通过 `/transition ANALYZING` 和 `/transition READY`；治理审计已确认 `ANALYZING -> READY`，当前标签为 `status:ready`，与本地任务状态一致。
- 远程 `main` 为 `d524b1218746133410c409134749fe7058ddf3b2`；Issue #6 和 PR #7 仍开放，PR #7 未合并。
- 控制塔已核对远程 `main` 树、GitHub 治理 READY 必备章节、当前文件依赖和生成物边界；`tests/fixtures/**/__pycache__` 明确排除。
- 本轮只写入本任务文件、`TASKS.md`、`CURRENT_TASK.md` 和 `PROJECT_STATE.md`；未修改产品文件、测试或稳定规则。
- 分析已达到 `READY`；本实施已建立隔离分支并按白名单迁移文件，尚未创建 PR 或验收线程，亦未启动任何 Dry-run。

## 下一步

实施线程 `20｜实施｜20260918-006` 正在按上述隔离工作树和白名单执行；完成验证、提交推送和 Draft PR 后进入 `READY_FOR_VERIFY`。

## 实施记录（2026-09-18）

- 已在隔离工作树从远程 `main` 建立 `codex/13-accepted-baseline-integration`；原始脏工作区未写入。
- 已按白名单迁移 9 个产品/测试/fixture 文件与 `docs/codex` 下 15 个 Markdown 文件；20 个未更新文件源/目标 SHA-256 逐项一致，4 个状态文档按契约更新。
- 已语义合并 `AGENTS.md`、`CHANGELOG.md`、`README.md`；三者需人工 diff 复核，不适用直接 hash 一致条件。
- 当前允许范围仍仅限任务契约中的白名单和三处语义合并文件；状态同步为 `IN_PROGRESS`。

### 直接迁移源 SHA-256 与核对结果

复制前记录的源文件 SHA-256；复制后 20 个未更新的直接迁移文件逐项一致，4 个状态文档按任务契约同步为 `IN_PROGRESS`：

| 文件 | SHA-256 |
| --- | --- |
| `src/quant_lab/release.py` | `7483a42ec91e6cb9999765bc005ebf6530ef0c7814613afc72b324a3e4989526` |
| `src/quant_lab/validation.py` | `9814192deb7e8db1b1c7f6ece7814ced9075a6d8dcd20241043c516736cd6522` |
| `src/quant_lab/dry_run.py` | `44ec4adde07466eb531d5619134533089d120862b32b8829c887a8ace5d6ca6` |
| `tests/test_release.py` | `5a37dfbaf0b7ce23df98cebed2f33f1913d696597dfe3012b3c2c13e90bbb91` |
| `tests/test_validation.py` | `8808e6d15401e470432fc48b119988c1505ee9f91d590f4e04c595880df663b4` |
| `tests/test_dry_run_supervisor.py` | `3326378af54fdc67e887472560276b3dc507ed30af17a44358af481e640aa03` |
| `tests/fixtures/validation_cli/CliCandidate.py` | `0db702e673b297b19b0f32d4d50d9a31b1b8cc8c0447012ad0c5b9699b349355` |
| `tests/fixtures/validation_cli/freqtrade.json` | `9baaf0dc6dbba38f60b7aa6294aab8ab1a52175d6dd04a3ad1948f59a7df417de` |
| `tests/fixtures/validation_cli/risk.toml` | `5280700034f23e191dfeefd24073cb12a4a2c7847a8931de580c61390157119` |

`docs/codex/` 下 11 个未更新 Markdown 文件的源/目标 SHA-256 逐项一致；`CURRENT_TASK.md`、`PROJECT_STATE.md`、`TASKS.md` 和本任务文件为状态更新例外。`AGENTS.md`、`CHANGELOG.md`、`README.md` 为语义合并例外，已人工复核。

### 实施验证

- 定向 pytest：`88 passed in 29.99s`。
- 全量 pytest：`93 passed in 31.45s`。
- Ruff：`All checks passed!`；`pip check`：`No broken requirements found.`；`compileall`：`PASS`；`git diff --check`：`PASS`。
- Freqtrade `2026.8` 合成 `list-strategies`：输出 `CliCandidate`，退出码 `0`；未启动 Dry-run、未下载行情、未连接交易所。
- 缺少 Freqtrade 可执行文件：退出码 `2`，结论 `evidence_insufficient`，六项检查均失败关闭，未执行交易命令；生成物已清理。
- 本机回环 HTTP/DOM：`1 passed, 23 deselected`；Playwright Python/Node 不可用，视觉检查未执行。
