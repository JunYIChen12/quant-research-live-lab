# 20260917-005 1.0 单正式 Dry-run 闭环分析

## 状态与责任

- 创建日期：2026-09-17，Asia/Shanghai。
- 状态：`CLOSED`。
- 当前责任线程：`00｜项目控制塔`。
- 唯一根目录：`D:/CodexProjects/projects/quant-research-live-lab`。
- 基线：分支 `codex/workbench-init`，HEAD `ba8738fe18289398a8c6713772416facddb5532d`。
- 来源：已关闭任务 `20260912-002` 的 1.0 实施顺序和 MVP 范围。

## 单一目标

在不启动 Freqtrade、不连接交易所、不读取真实凭据的前提下，把“单个正式 Dry-run + 最小本机 Web 管理台 + 轮次监督”整理成可实施、可独立验收的最小契约。

## 已确认范围

- 只支持一个正式 Dry-run 实例和一个活动轮次。
- 首版杠杆保持 1 倍，正式仓位数量保持最多一个。
- Web 只监听本机回环地址，只提供一个工作页面。
- 用户只在 Web 填写轮次参数、批准正式冻结版本、停止或重新授权。
- 订单、持仓、成交、费用和余额继续以 Freqtrade 为事实源；项目 SQLite 只保存最小监督状态。
- 硬亏损、到期、达标、主动结束、平仓核对、重启恢复和 Codex 不可用必须失败关闭或保持暂停。
- 本任务不进入候选并发、自动研究循环、实盘、多正式策略或远程访问。

## 分析范围

1. 明确轮次状态机、启动前检查和 Freqtrade REST API 的调用边界。
2. 明确四项输入、计时、净盈利、净亏损、平仓核对和停止优先级的可执行规则。
3. 明确本地 SQLite 的最小字段、幂等恢复和不得复制的交易事实。
4. 明确 Web 页面动作、后台状态、通知和异常时的用户可见结果。
5. 为实施切片拆分允许修改文件、保持不变项、验证命令和九类核心验收场景。

## 不在范围

- 不实现代码、Web、Windows 通知或 Freqtrade 运行服务。
- 不选择新的交易引擎，不修改安全模型或发布政策。
- 不确定盈利阈值、杠杆扩张、多策略并发或实盘授权。
- 不下载行情、不连接交易所、不读取账户数据或凭据。

## READY 条件

- 轮次状态、输入输出、失败关闭和恢复规则无冲突。
- Web 与后台职责、Freqtrade 事实源和 SQLite 最小状态边界明确。
- 每个关键规则都有可复核验收场景和验证方法。
- 允许修改范围、保持不变项和停止条件完整。
- 用户未确认的数值或产品取舍明确标记为待确认，不用默认值代替。

## 下一步

分析已收口并通过 READY 一致性检查。当前由唯一实施线程按白名单落地并验证；本任务不自动启动 Dry-run，验收线程仅在 `READY_FOR_VERIFY` 后创建。

## 已确认规则

### 启动流程

1. 用户填写模拟本金、目标净盈利、有效时长和最大净亏损。
2. 系统展示已通过验证的冻结策略。
3. 用户选择一个策略并批准。
4. 系统核对策略文件、配置、验证报告和 GitHub 批准记录是否一致。
5. 核对通过后，系统自动启动 Freqtrade Dry-run。
6. 任一核对失败，系统保持暂停并告诉用户原因。

用户只负责填写参数和批准策略；启动前检查与启动动作由系统完成。

## 仓库与运行基线

- 本次只读核对的仓库事实：cwd 为 `D:/CodexProjects/projects/quant-research-live-lab`，分支为 `codex/workbench-init`，HEAD 为 `ba8738fe18289398a8c6713772416facddb5532d`；远程为 `https://github.com/JunYIChen12/quant-research-live-lab.git`。
- `.venv/Scripts/freqtrade.exe --version` 返回 `freqtrade 2026.8`；Python 为 3.12.10，CCXT 为 4.5.78。未启动服务，未连接交易所，未读取真实凭据。
- 当前已有未提交修改由其他工作保留；本次唯一写入对象为本任务文件。`release.py`、`validation.py` 当前没有 Web、监督状态机或 Freqtrade REST 客户端实现。

## Freqtrade 2026.8 REST 契约

以下均以官方 2026.8 标签的一手文档或源码为准，不能用本项目 SQLite 或 HTTP 返回码替代实际状态核对。

- 文档：[REST API](https://raw.githubusercontent.com/freqtrade/freqtrade/2026.8/docs/rest-api.md)、[configuration](https://raw.githubusercontent.com/freqtrade/freqtrade/2026.8/docs/configuration.md)；源码：[api_trading.py](https://raw.githubusercontent.com/freqtrade/freqtrade/2026.8/freqtrade/rpc/api_server/api_trading.py)、[rpc.py](https://raw.githubusercontent.com/freqtrade/freqtrade/2026.8/freqtrade/rpc/rpc.py)、[api_auth.py](https://raw.githubusercontent.com/freqtrade/freqtrade/2026.8/freqtrade/rpc/api_auth.py)、[api_schemas.py](https://raw.githubusercontent.com/freqtrade/freqtrade/2026.8/freqtrade/rpc/api_schemas.py)。API 版本源码为 `2.50`。
- `/api/v1/ping` 不需要认证，只返回 `{"status":"pong"}`，只证明 API 可达；其他敏感端点需要 HTTP Basic 或 JWT。登录为 `/api/v1/token/login`，访问令牌有效期为 15 分钟，刷新令牌有效期为 30 天。1.0 的 API URL、用户名和密码只通过启动进程的运行时环境注入，不能进入仓库、SQLite、普通日志或 Web 响应。
- `/start` 是状态变更请求，返回 `starting trader ...` 或 `already running`，不是启动完成证明。必须随后核对 `/health`、`/show_config`、`/status` 和运行身份；`/show_config` 必须证明 `dry_run=true`、杠杆/仓位限制和冻结配置符合批准版本。
- `/pause` 将状态置为暂停并禁止新入场；重复调用是状态设置，不应被当成一次新的业务事件。`/stop` 将 bot 停止，但不负责平掉持仓；`cancel_open_orders_on_exit` 也不会影响开放持仓。
- `/stopbuy` 在文档中描述为停止新仓并按规则优雅处理开放仓位，但 2026.8 源码把 `/stopbuy` 映射到与 `/pause` 相同的处理器。因此实施不得仅依赖 `/stopbuy` 的文档描述，统一使用 `/pause` 后核对实际状态和订单。
- `/status` 返回开放交易；无活动交易时源码捕获 `RPCException` 并返回空数组。开放交易包含 `current_rate`、`profit_abs`、`profit_ratio`、`total_profit_abs`、`total_profit_ratio`、订单和成交信息。`/trades` 默认最多 500 条、支持 `limit`/`offset`，用于取已关闭交易和订单历史，必须处理分页。
- `/forceexit` 仅表示已创建退出订单：单笔返回 `Created exit order...`，`tradeid=all` 返回 `Created exit orders for all open trades.`；源码不会在 `all` 分支等待所有订单成交。它可能先取消入场单，再创建退出单，因此调用后必须继续轮询 `/status`、交易订单和已关闭交易，不能以响应成功作为平仓成功。
- `DELETE /trades/{id}/open-order` 只取消指定交易的开放订单；调用后仍需重新读取订单。不得使用删除交易记录的接口来伪造平仓。
- `/profit` 是累计统计，包含符合选择条件的历史已关闭交易和当前开放交易，不提供本轮天然隔离的 round id；`profit_abs`、`close_profit_abs`、费用等字段应结合本轮边界核对。`/balance` 返回钱包与起始资本的当前视图，Dry-run 钱包由 `dry_run_wallet` 模拟。
- Dry-run 不向交易所下单；市场模拟受订单簿和最大 5% 滑点规则影响，限价单按成交/超时规则处理，重启后开放订单默认假定离线期间未成交。这些是引擎事实，不能被项目层的“已启动”或 SQLite 状态覆盖。

## 批准到启动的绑定

`release.py` 的 `verify_release` 是启动闸门，不是 SQLite 字段校验。正式启动必须在同一事务意图中保存并核验以下绑定：

1. 用户选择的冻结版本对应 manifest 的 `approved_commit_sha`、`release_tag`、`repository`、策略/风险/验证报告路径和 SHA-256；Git HEAD、注释 tag 目标、tag 中的 manifest hash、所有 artifact 路径和 hash 均精确匹配。
2. `approval_pr_number` 必须大于 0；GitHub PR 必须已合并到 `main`，`merge_commit_sha` 必须等于批准 commit，并含 `release-approved` label。GitHub 检查不可达、字段缺失、PR 未合并、分支/commit/label 不符，均为拒绝；`approval_pr_number=0` 永远不是授权。
3. 当前 Web 批准记录只作审计关联，不能单独授权；启动前再次执行完整 release 验证，且每次允许新入场前仍要确认发布校验和运行前检查未失效。SQLite 中不保存可绕过 GitHub/release 检查的布尔授权。
4. 验证通过后才允许从 `APPROVAL_PENDING` 进入 `STARTING` 并调用 `/start`。版本、策略、有效配置、验证报告、仓库 HEAD、tag、PR 状态或文件 hash 任一改变，批准立即失效，状态转为 `BLOCKED/PAUSED`，不自动切换、不恢复旧策略。
5. 启动完成的判定必须同时满足：Freqtrade API 认证成功、有效配置为 Dry-run、目标策略/配置已加载、bot 健康、没有需要处理的旧持仓或已进入明确的 reconcile 等待；HTTP 200、`/ping`、`starting trader` 或 SQLite 的 `approved=true` 均不足以证明启动完成。

## 四项输入的最小校验

四项输入必须使用同一 stake currency 和明确的小数精度，以一次原子提交创建轮次；任何一项无效都不写入可启动状态。

| 输入 | 最小契约 | 启动后规则 |
| --- | --- | --- |
| 模拟本金 | 同冻结 `stake_currency` 的十进制字符串，有限、非 NaN/Infinity、非科学计数法、严格大于零，且必须与本轮有效配置的 `dry_run_wallet` 精确一致；不能精确表示时拒绝。 | 轮次开始后固定，不允许增加、减少或用追加资金覆盖。 |
| 目标净盈利 | 同币种的十进制字符串，有限、严格大于零，不提供默认值，不静默舍入。 | `RUNNING` 中可按 R51-R52 与总有效时长原子修改；在 `CLOSING`/`RECONCILING` 冻结，修改不清除已实现 PnL。 |
| 有效时长 | Web 输入严格大于零的整数分钟，内部保存为整数秒；无默认值、无业务最大值，解析溢出时拒绝。 | 从首次确认的模拟开仓成交开始计时；按 R52 修改本轮总时长，不重置已消耗时间。 |
| 最大净亏损 | 同币种的十进制字符串，有限、严格大于零、不大于模拟本金，不提供默认值，不静默舍入。 | 在轮次开始时冻结；用户、系统和研究流程均不能在运行中放宽。达到阈值后永久锁定本轮。 |

跨字段还必须拒绝 NaN/Infinity、科学计数法、零值/负值、币种不一致、最大净亏损大于本金、无法精确映射到有效 Freqtrade 配置或会导致单仓限制失效的组合。实现不得补充隐藏默认值或静默舍入。

## PnL、退出成本与计时

- Freqtrade `/profit` 不是本轮指标。实施保存 `start_trade_id_max`、`started_at_utc` 和 `starting_balance` 三个边界摘要，以 `trade_id > start_trade_id_max` 为主要归属规则，并用开仓时间和余额变化交叉核对；不得复制独立交易账本，冲突时失败关闭。
- “当前估计净盈利”应表示：本轮已实现结果，加上开放仓位按当前可验证价格平仓后的结果，减去预计平仓费用、资金/利息费用（若适用）和保守不利滑点。该值只能触发“先暂停入场、再平仓、再核对”的流程。
- 最终净盈利只能在所有开放仓位和入场订单处理完、交易关闭记录与费用字段核对完成后确定。达标估计但实际低于目标时，若仍有剩余有效时间且未触发硬亏损，继续同一轮，不清零、不重置计时、不保证最终达标；超出目标保留，不为追求更高目标而继续入场。
- “保守退出成本”覆盖实际关闭手续费、可验证资金费/利息和冻结 `risk_config.exit_cost_buffer_bps`；该字段随发布制品哈希绑定，缺失、负数或不可解析即阻塞。不得从官方 5% Dry-run 上限自行推导固定扣减，也不得临时改变冻结退出类型。
- 硬亏损估计为“起始本金减去现在全部平仓后预计剩余资金”，包含已实现/未实现结果和保守退出成本；当估计亏损 `>=` 最大净亏损时停止新入场、退出开放仓位并持久化永久锁。
- 计时从首次模拟开仓成交确认开始。首次成交前等待不计时；首次成交后，可靠行情和状态下的普通空仓等待计时；`WAITING_FOR_STRATEGY`（账户平、无合格策略）、PC 关闭/进程重启间隙、市场数据不可靠和无法完成核对时暂停计时并禁止新入场。`CLOSING`/`RECONCILING` 消耗剩余有效时间，零时间不重新开放。
- 重启或网络恢复先核对最新可靠状态，不把离线期间未知的越界时间追溯成新的锁；但已有锁不得清除。无法证明状态、订单或成交边界时保持 `BLOCKED`，不启动、不入场。

## 最小状态机与事件优先级

确认的最小状态为：`APPROVAL_PENDING`、`STARTING`、`RUNNING`、`WAITING_FOR_STRATEGY`、`CLOSING`、`RECONCILING`、`COMPLETED_TARGET`、`COMPLETED_TIMEOUT`、`STOPPED_USER`、`STOPPED_LOSS_LOCK`、`BLOCKED`。实现可调整内部名称，但不得放宽语义。

固定优先级（从高到低）为：已证明的发布/状态完整性失败 -> 硬亏损 -> 用户结束 -> 有效时长到期 -> 达标估计 -> 等待合格策略 -> 正常入场信号。同一快照只执行最高优先级的一次关闭意图，但记录所有观察原因；硬亏损终态原因不得被覆盖。

`CLOSING` 只允许一次关闭意图；`RECONCILING` 只允许读状态和完成已存在的退出流程。退出完成的最低条件是：没有开放持仓、没有未处理入场/退出订单、关闭交易记录和费用可读、最终余额/PnL 已绑定到本轮。失败显示处理中/异常并保持暂停或阻塞，不显示成功。

## 轮询、重试、幂等与重启

- 1.0 固定预算为：HTTP 请求超时 5 秒、正常轮询间隔 2 秒、启动确认窗口 60 秒、关闭核对窗口 300 秒；GET 最多重试 3 次，退避为 1、2、4 秒。超过窗口按已确认方案进入 `BLOCKED` 或 `RECONCILING/BLOCKED`，不得显示成功。
- GET 读操作可在预算内重试；每次响应都记录时间、端点、状态码和摘要 hash。`/start`、`/pause`、`/forceexit` 没有项目级 idempotency key：`/start`/`/pause` 可按状态重复确认，但 `forceexit` 在响应不确定时不能盲目重放。
- 每个状态变更意图先在 SQLite 持久化唯一 `action_id`、期望状态和 round id，再发 REST 请求；响应超时后先读 `/health`、`/show_config`、`/status`、订单/交易历史进行核对，只有仍有未处理对象且在关闭预算内才可重试。任何重复调用都不得重复计算 PnL 或生成第二个业务关闭事件。
- 重启恢复顺序固定为：加载本轮参数和锁 -> 不允许新入场 -> 认证并读取健康/有效配置 -> 读取持仓、订单、交易历史、余额 -> 对比最后可靠观察和未完成 action -> 继续关闭或进入 `RUNNING`。终态轮次保持暂停/锁定；待处理关闭轮次不重新发起新的 round。
- SQLite 只保存 round/release/approval/time/lock/action/last-observation 等监督状态和审计摘要，不复制 Freqtrade 交易事实。对账冲突、未知成交、配置漂移、认证失败、API 不可达或证据过期均失败关闭。

## 九类核心验收场景

| 场景 | 状态转换 | 输入/事件 | 预期结果 | 独立证据 |
| --- | --- | --- | --- | --- |
| 1. 证据不足 | `APPROVAL_PENDING -> BLOCKED` | 报告缺失/过期/hash 不符，或 GitHub 批准不可证实 | 禁止 `/start`，批准按钮不可完成，展示具体原因 | release 验证 violation、manifest/artifact hash、无 `/start` 调用记录、SQLite 状态 |
| 2. 估计达标但结算不足 | `CLOSING -> RECONCILING -> RUNNING` | 估计值达到目标，实际结算低于目标，时间/风险仍足够 | 保留已实现 PnL，继续同一轮；不重置计时、不追加资金 | force-exit 响应、status 为空的时点、closed trade/费用、余额、状态和计时快照 |
| 3. 正常达标 | `RUNNING -> CLOSING -> RECONCILING -> COMPLETED_TARGET` | 最终净盈利达到目标 | 无开放仓/订单，轮次暂停并记录最终结果，不再新入场 | 退出 action、status 空数组、订单无开放项、交易关闭字段、最终余额/PnL、round 记录 |
| 4. 到期与新信号同刻 | `RUNNING -> CLOSING` | 有效时长到点且同时出现入场信号 | 到期优先，拒绝新入场并开始退出 | 单调/持久计时记录、到期前后信号、无到期后新入场订单、状态转换 |
| 5. 硬亏损 | `RUNNING -> CLOSING -> STOPPED_LOSS_LOCK` | 保守平仓亏损达到最大净亏损 | 立即停入场、退出全部开放仓、永久锁；普通恢复无权清除 | 风险计算输入/结果、pause/force-exit、关闭核对、锁字段、重启后仍锁定 |
| 6. 部分平仓后重启 | `CLOSING/RECONCILING -> RECONCILING` 或 `BLOCKED` | 退出未完全成交，进程重启 | 先禁止入场并核对剩余持仓/订单，再继续未完成退出；不重复计 PnL/业务事件 | 重启前后 status/orders/trades、action_id、关闭请求次数、最终单笔成交/费用 |
| 7. 用户主动结束 | `RUNNING -> CLOSING -> STOPPED_USER` | 用户明确结束本轮 | 停止新入场、取消未成交入场单、退出开放仓并核对；不追逐目标 | Web 审计事件、REST 响应、订单/持仓清空、最终结算和结束原因 |
| 8. 冻结版本被篡改 | `APPROVAL_PENDING/STARTING -> BLOCKED` | commit/tag/manifest/config/report/artifact/PR label 任一漂移 | 批准失效，禁止启动/切换，不恢复旧策略 | HEAD/tag/manifest/artifact/PR 核对、violation、无启动或入场、审计摘要 |
| 9. Codex 不可用 | `RUNNING -> RUNNING`（研究支路暂停） | Codex/研究服务不可达，Freqtrade 和监督状态仍健康 | 不改变正式轮次的锁、PnL、计时或仓位；研究停止并告警 | 监督健康与 REST 状态、Codex 错误、无状态/订单变化；若正式状态也不可信则转 `BLOCKED` |

## 实施边界与保持不变项

下一责任线程只允许在 `src/quant_lab/` 增加最小监督、REST 适配、状态持久化代码，在 `tests/` 增加对应单元/伪 REST/重启回归测试；必要时才改 `pyproject.toml`，配置只允许提交无秘密的 example。不得修改 Freqtrade 核心、策略、`release.py`、`validation.py`、安全模型、发布政策、1.1 候选并发或真实交易适配器，除非控制塔另开并批准独立任务。不得覆盖现有未提交修改。

保持不变：Freqtrade 2026.8 为目标版本；单一正式轮次；杠杆 1 倍、最多一仓；本机回环 Web；Freqtrade 是交易事实源；SQLite 仅保存监督状态；`release-approved` 与精确 commit/hash 绑定；研究、Dry-run、live 数据物理隔离；无真实凭据、交易所连接和远程访问。

实施后的最小验证顺序：`git status --short` 和 `git diff --check`；针对输入/状态/幂等/重启的 `.venv/Scripts/python.exe -m pytest`；`.venv/Scripts/ruff.exe check .`；`.venv/Scripts/python.exe -m pip check`；`compileall`；使用伪 REST 服务验证九类场景；最后用 Playwright 验证本机 Web。不得把 `/ping`、HTTP 200、SQLite `approved`、启动响应或历史事件当作业务成功；本任务本身不启动真实 Dry-run 验收。

实施中以下任一条件出现即停止并按工作流转 `BLOCKED`：需要写入白名单外文件、需要读取/注入真实交易凭据、连接交易所、启动真实 Dry-run、改变发布/安全边界、官方语义与本文件冲突、无法证明本轮 PnL 归属或保守退出成本，或无法实现可审计的重试/重启行为。

## 已确认决定与状态结论

2026-09-17，用户确认下列控制塔最小方案。此前关于输入、轮次归属、退出成本、REST 预算、认证、事件优先级和重新授权的实现选择已经关闭；具体本金、盈利目标、时长、最大亏损和策略参数仍由用户按轮次或冻结发布填写，不在本任务中硬编码。

## 已确认控制塔最小方案

### 1. 四项输入

- 币种固定取冻结 runtime config 的 `stake_currency`，Web 不提供币种切换。
- 金额输入按十进制字符串解析，必须有限且严格大于零；禁止 NaN、Infinity、科学计数法和静默舍入。若不能被 Freqtrade 有效配置精确表示，直接拒绝。
- 模拟本金必须与本轮有效配置的 `dry_run_wallet` 精确一致。启动层只允许生成一个记录了 round id 和摘要的临时配置覆盖，不修改冻结制品；有效配置核对不一致即阻塞。
- 目标净盈利与最大净亏损使用同一 stake currency；最大净亏损不得大于模拟本金。目标净盈利、最大净亏损均不提供默认数值。
- Web 的有效时长以正整数分钟输入，内部保存为整数秒；不提供默认值，不设置业务最大值，但拒绝解析溢出。
- 轮次启动后本金和最大净亏损固定。`RUNNING` 时仅允许目标净盈利和总有效时长一次原子修改；按既有 R51-R52 立即用同一可靠快照重算。进入 `CLOSING` 或 `RECONCILING` 后冻结，修改不排队。

### 2. 本轮交易归属

- 启动前必须确认没有开放持仓和未处理订单；否则进入 `RECONCILING/BLOCKED`，不得建立新轮次边界。
- SQLite 只保存 `start_trade_id_max`、`started_at_utc` 和 `starting_balance` 三个边界摘要，不复制订单、成交或持仓记录。
- 本轮交易以 `trade_id > start_trade_id_max` 为主要归属规则；开仓时间不得早于 `started_at_utc`，余额变化必须能与本轮交易和费用对上。时间和余额只作交叉核对，不能单独把交易归入本轮。
- 发现 ID、时间、余额或交易历史冲突时失败关闭，不猜测归属，也不通过修改 SQLite 修正 Freqtrade 事实。

### 3. 净收益与保守退出成本

- 已实现净收益直接汇总本轮 Freqtrade 已关闭交易的实际利润、入场/退出手续费、资金费和利息字段。
- 开放仓估值使用 Freqtrade 当前可验证状态，并额外扣除冻结 `risk_config` 中的 `exit_cost_buffer_bps`。该参数必须随发布制品哈希绑定，不是 Web 输入，也不能在轮次中修改；缺失、负数或不可解析即阻塞。
- 普通目标和到期按冻结 runtime/risk config 的退出订单类型处理；硬亏损按冻结的 emergency exit 规则处理。项目层不从 Freqtrade 的 5% Dry-run 行为推导固定扣减，也不临时改变市价/限价策略。
- 最终净收益只在无开放持仓、无未处理订单、关闭交易及实际费用可读后确定。估计达标只触发关闭核对，不直接宣布完成。

### 4. REST、重试与认证

- 1.0 默认预算：单请求超时 5 秒，正常轮询间隔 2 秒，启动确认窗口 60 秒，关闭核对窗口 300 秒；GET 最多重试 3 次，退避为 1、2、4 秒。
- 超过启动窗口转 `BLOCKED`；超过关闭窗口保持暂停并转 `RECONCILING/BLOCKED`，不得显示成功，也不得盲目重放 `/forceexit`。
- `/start`、`/pause` 在读取实际状态后才允许重试；`/forceexit` 响应不确定时先核对持仓、订单和交易历史，仅在确认仍有未处理对象且 action id 未完成时继续。
- Freqtrade API URL、用户名和密码只通过启动进程的运行时环境注入；不得写入 Git、SQLite、普通日志或 Web 响应。1.0 不引入 Credential Manager、Vault 或新的秘密服务；需要更强秘密托管时另立任务。

### 5. 事件优先级与重新授权

- 固定优先级：已证明的发布/状态完整性失败 -> 硬亏损 -> 用户结束 -> 有效时长到期 -> 达标估计 -> 等待策略 -> 正常入场。
- 同一快照触发多个事件时只执行最高优先级的一次关闭意图，同时记录所有观察到的原因；硬亏损的终态原因不得被用户结束、到期或达标覆盖。
- `STOPPED_LOSS_LOCK`、`STOPPED_USER`、`COMPLETED_TIMEOUT`、`COMPLETED_TARGET` 和已证明制品漂移均为本轮终态，不恢复原轮次；重新授权必须创建新 round id，并重新完成冻结版本和 GitHub 批准核对。
- API、GitHub 或市场状态暂时不可验证时进入暂停/阻塞，但不直接伪造终态。恢复后只有在制品未漂移、交易归属可核对、没有终态锁且有效时长仍有剩余时，才允许恢复同一轮。

### READY 一致性结论

该方案复用现有 Freqtrade、`risk_config` 哈希和 release 验证，不新增交易账本、秘密平台或通用工作流。目标、范围、保持不变项、九类验收场景、验证方法、实施白名单和停止条件已完整且互相一致，没有会显著改变实现的未决选择。任务于 2026-09-17 流转为 `READY`；仅允许控制塔下一步创建唯一实施线程。

### 本次验证记录

- 已核对任务文件和引用的 MVP/需求/发布/安全文档；迁移目录没有未吸收的正式记录。
- 已核对目标版本命令输出和官方 2026.8 文档/源码语义；未启动服务，未运行 Dry-run，未连接交易所，未读取真实凭据。
- 用户确认五组最小方案后，控制塔完成 READY 一致性检查并同步任务状态文件；未修改产品代码、未启动服务、未创建实施或验收线程。

### 下一责任线程

`30｜验收｜20260917-005`：独立复核实施结果、九类伪 REST 场景、状态持久化边界和本机 Web；不得启动正式 Dry-run。

## 实施交付记录

- 交付状态：`READY_FOR_VERIFY`；未标记 `ACCEPTED`。
- 实现文件：`src/quant_lab/dry_run.py`、`tests/test_dry_run_supervisor.py`。
- 同步文件：本文件、`docs/codex/CURRENT_TASK.md`、`docs/codex/TASKS.md`。
- 保持不变：`src/quant_lab/release.py`、`src/quant_lab/validation.py`、Freqtrade 核心、策略、发布/安全政策、候选并发和真实交易适配器；既有未提交修改未清理、未回退、未覆盖。
- 实现范围：严格十进制输入和 `dry_run_wallet` 核对；`risk_config.exit_cost_buffer_bps`；单轮 SQLite 监督状态/动作/观察摘要/事件；Freqtrade 2026.8 REST 路由、认证环境注入、固定超时/重试预算和逐响应摘要审计；状态优先级、交易 ID 边界、余额交叉核对、停止/平仓核对、幂等恢复、重新授权和本机回环单页 Web。
- 伪 REST：状态场景测试替身继承真实 `FreqtradeRestClient`，由内存 opener 提供 `/health`、`/show_config`、`/status`、分页 `/trades`、`/balance` 和 `/start`、`/pause`、`/forceexit` 响应；九类验收场景均通过该边界运行。另有逐响应审计回归，确认成功与 HTTP 错误均写入 SQLite 的端点、状态码和摘要哈希。

### 验证证据

- 初始 TDD 红灯：实现前运行 `.venv\Scripts\python.exe -m pytest tests/test_dry_run_supervisor.py`，收集阶段因 `quant_lab.dry_run` 不存在失败。
- 相关测试：`.venv\Scripts\python.exe -m pytest tests/test_dry_run_supervisor.py -q`，`20 passed`。
- 全量测试：`.venv\Scripts\python.exe -m pytest`，`42 passed`。
- 静态/环境检查：`.venv\Scripts\ruff.exe check .` 通过；`.venv\Scripts\python.exe -m pip check` 返回 `No broken requirements found.`；`.venv\Scripts\python.exe -m compileall -q src tests` 通过；`git diff --check` 通过。
- 本机 Web：Playwright Python/Node 包均不可用，未伪称 Playwright 通过；按浏览器测试技能用 CUA 等价运行时检查，在临时回环端口 `52645` 验证页面标签、ARIA 状态、创建轮次和无控制台错误。默认端口 `8765` 已被既有本机“每日待办”程序占用，未停止或改动该程序。

### 未执行、限制与剩余风险

- 未启动正式 Freqtrade、未连接交易所、未下载行情、未读取或生成真实凭据；因此没有真实账户、交易、盈利或实盘授权证据。
- Playwright 依赖缺失，精确 Playwright 命令跳过；浏览器等价检查不替代验收线程的独立复核。
- 当前工作区仍有其他线程/用户既有修改，未将其混入本任务结论；未提交、未推送、未创建 PR。
- 验收复现：在项目根目录运行上述测试和检查；使用 `create_web_server(..., host="127.0.0.1", port=0)` 做本机页面检查；使用 `FreqtradeRestClient` 的内存 opener 复现 REST 分页、错误、重试和逐响应观察记录。

## 独立验收结果（2026-09-18）

### 结论

- 状态：`REWORK`。
- 验收线程：`30｜验收｜20260917-005`。
- 验收基线：cwd `D:/CodexProjects/projects/quant-research-live-lab`；分支 `codex/workbench-init`；HEAD `ba8738fe18289398a8c6713772416facddb5532d`；origin `https://github.com/JunYIChen12/quant-research-live-lab.git`。
- 启动门禁：`CURRENT_TASK.md`、`TASKS.md`、本任务文件均为 `READY_FOR_VERIFY`，责任线程匹配；验收开始前已核对父级/项目规则、工作流、状态、任务、MVP/需求、治理/发布/安全文档和 migration（无未吸收记录）。
- 当前工作区已有未提交修改，未清理、未回退、未提交、未推送；验收只回写本任务文件、`CURRENT_TASK.md` 和 `TASKS.md`。

### 必须返工的问题

1. **有效配置的杠杆不是 1 倍时仍允许启动。**
   - 文件/行：`src/quant_lab/dry_run.py:1665-1700`，`_runtime_issues()` 只在 `runtime_config` 提供同名字段时比较，未强制 `snapshot.config["leverage"] == 1`；`runtime_config` 未提供 `leverage` 时完全放行。
   - 复现：独立伪 REST 场景中使用 `snapshot(..., config={"leverage": 2})`，再调用 `approve_and_start()`。
   - 预期：`BLOCKED`，且无 `/start`。
   - 实际：`RUNNING`，`/start` 调用次数为 `1`。
   - 影响：违反项目安全模型和 1.0 固定杠杆边界，必须失败关闭。

2. **`/start` 不确定响应未先核对运行状态。**
   - 文件/行：`src/quant_lab/dry_run.py:1255-1270`，`approve_and_start()` 捕获异常后直接标记 `UNKNOWN` 并 `_block("start_request_uncertain")`，没有按契约先读取 `/health`、`/show_config`、`/status`、交易历史和余额。
   - 复现：伪 REST 的 `/start` 抛出 `TimeoutError`，其余 GET 可返回健康且 Dry-run 配置有效；调用 `approve_and_start()`。
   - 预期：保留 `STARTING`，先完成启动状态核对，再按窗口决定确认、重试或阻塞；不能留下未核对的运行实例。
   - 实际：直接进入终态 `BLOCKED`，观察调用只有启动前快照和 `/start`，没有启动后核对 GET。
   - 影响：超时但服务端已启动时，监督器可能把正式实例留在运行状态却不再监督；违反不确定 POST 的恢复契约。

3. **硬亏损关闭期间的发布漂移覆盖了更高优先级的完整性失败。**
   - 文件/行：`src/quant_lab/dry_run.py:2076-2080`，`_reconcile()` 仅在 `not record.loss_lock` 时处理 `integrity`；硬亏损锁已置位后，发布制品漂移被忽略。
   - 复现：先以 `profit=-200` 触发 `CLOSING`/`loss_lock=True`，再让 release check 返回 `artifact_hash_mismatch`，随后提交已关闭交易和余额 `800` 的快照。
   - 预期：按固定优先级转 `BLOCKED`，记录发布完整性失败。
   - 实际：转 `STOPPED_LOSS_LOCK`，原因仍为 `loss_lock`。
   - 影响：违反“发布/状态完整性失败高于硬亏损”的优先级，可能把冻结制品漂移误报成正常硬停机完成。

建议返回 `20｜实施｜20260917-005`，只在已批准实现范围内修复上述根因，并补充对应失败测试；不得由验收线程自行修改产品代码。修复后重新执行独立验收。

### 独立验证证据

| 检查 | 实际结果 |
| --- | --- |
| `.venv\\Scripts\\python.exe -m pytest tests\\test_dry_run_supervisor.py -q` | `20 passed` |
| `.venv\\Scripts\\python.exe -m pytest -q` | `42 passed` |
| `.venv\\Scripts\\ruff.exe check .` | `All checks passed!` |
| `.venv\\Scripts\\python.exe -m pip check` | `No broken requirements found.` |
| `.venv\\Scripts\\python.exe -m compileall -q src tests` | 退出码 `0` |
| `git diff --check` | 退出码 `0` |
| 独立伪 REST：估值达标后结算不足、正常达标、到期优先、硬亏损锁、部分平仓重启、用户停止、余额冲突、Codex 不可用、重新授权 | 已有场景全部通过；上述三项额外安全场景失败 |
| 独立 REST 预算/认证/分页/审计摘要 | 固定超时、GET 重试退避、运行时环境凭据、分页历史和逐响应摘要检查通过；未读取真实凭据 |
| 本机 Web | HTTP/DOM 结构检查通过：绑定 `127.0.0.1`、单页标题、四项输入、`aria-live`、状态响应不含伪凭据；Playwright 不可用，未执行视觉验收 |

### 失败/跳过项与剩余风险

- 未启动 Freqtrade Dry-run 或交易服务，未连接交易所，未下载行情，未读取或生成真实交易凭据/账户导出；因此没有真实交易、盈利或实盘授权证据。
- Playwright Python/Node 包不可用；本轮只完成 HTTP/DOM 结构验收，不宣称视觉验收通过。
- 未修改 `src/`、`tests/`、配置、策略、发布/安全政策或任何产品文件；实施新增文件与已有 `release.py`、`validation.py` 及其测试/文档修改的时间归属以当前工作区和任务记录分离，不据此扩大范围。
- 代码体积不是本次失败依据；本次 `REWORK` 仅由可复现的杠杆强制门禁、启动不确定响应核对和完整性优先级契约错误触发。

### 下一责任线程

`20｜实施｜20260917-005`：修复三项根因并补回归测试，完成后将任务重新交回 `READY_FOR_VERIFY`；之后由新的 `30｜验收｜20260917-005` 独立复验。

## 返工交付记录（2026-09-18）

- 返工状态：`READY_FOR_VERIFY`；未标记 `ACCEPTED`。
- 根因一（有效配置杠杆）：`_runtime_issues()` 现在始终解析快照有效配置的 `leverage`；缺失/不可解析为 `leverage_invalid`，非 1 为 `leverage_must_be_one`，共同门禁在启动确认和运行核对中生效。
- 根因二（启动不确定响应）：`/start` 异常后先标记 action `UNKNOWN` 并读取完整快照；读回失败时保持 `STARTING`，由固定 60 秒窗口决定阻塞，`tick` 和恢复路径不再提前终态阻塞；确认安全状态后可进入 `RUNNING`，不盲目重放 `/start`。
- 根因三（完整性优先级）：发布/状态完整性失败无论是否已有 `loss_lock` 都记录并提升为优先原因；关闭理由按统一优先级保留完整性原因，`BLOCKED` 不再被亏损锁改写为 `STOPPED_LOSS_LOCK`，已有锁字段仍保留。
- 修改文件：`src/quant_lab/dry_run.py`、`tests/test_dry_run_supervisor.py`、本任务文件、`docs/codex/CURRENT_TASK.md`、`docs/codex/TASKS.md`。未修改 `release.py`、`validation.py`、策略、Freqtrade 核心、发布/安全政策或其他历史任务文件。

### 返工红灯与验证

- 三项验收复现测试先于修复运行：杠杆场景实际为 `RUNNING`、启动超时实际为终态 `BLOCKED`、亏损锁加发布漂移实际为 `STOPPED_LOSS_LOCK`；命令退出码为 1。
- 启动窗口补充测试先于窗口路径修复运行：启动后读回不可用在 59 秒时实际提前进入 `BLOCKED`；命令退出码为 1。
- 修复后目标四项测试：`.venv\Scripts\python.exe -m pytest tests/test_dry_run_supervisor.py::test_effective_leverage_must_be_one_even_without_runtime_expectation tests/test_dry_run_supervisor.py::test_uncertain_start_is_reconciled_before_any_block tests/test_dry_run_supervisor.py::test_uncertain_start_waits_for_startup_deadline_when_readback_fails tests/test_dry_run_supervisor.py::test_release_integrity_failure_wins_over_existing_loss_lock -q`，`4 passed`。
- 相关回归：`.venv\Scripts\python.exe -m pytest -o addopts='' tests/test_dry_run_supervisor.py`，收集 24 项，`24 passed in 22.19s`。
- 全量回归：`.venv\Scripts\python.exe -m pytest -o addopts=''`，收集 46 项，`46 passed in 30.05s`。
- 交付检查：`.venv\Scripts\ruff.exe check .` 通过；`.venv\Scripts\python.exe -m pip check` 返回 `No broken requirements found.`；`.venv\Scripts\python.exe -m compileall -q src tests` 退出码 0；`git diff --check` 退出码 0。
- 敏感信息/意外产物：凭据模式扫描无匹配；测试中的 `runtime-password` 仅为既有占位字面量，未读取或生成真实凭据。工作区其他既有修改保持原样。

### 未执行项与剩余限制

- 未启动正式 Freqtrade、未连接交易所、未下载行情、未读取账户或真实交易凭据；没有真实交易、盈利或实盘授权证据。
- Playwright Python/Node 依赖仍不可用；本次返工未改 Web，未重复浏览器检查，保留此前 HTTP/DOM 限制。

### 下一责任线程

`30｜验收｜20260917-005`：独立复验三项返工根因和全量回归证据；不得启动正式 Dry-run。

## 第二次独立验收结果（2026-09-18）

### 结论

- 状态：`ACCEPTED`。
- 验收线程：`30｜验收｜20260917-005`。
- 下一责任线程：`00｜项目控制塔`；不得直接标记 `CLOSED`。
- 验收基线：cwd `D:/CodexProjects/projects/quant-research-live-lab`；分支 `codex/workbench-init`；HEAD `ba8738fe18289398a8c6713772416facddb5532d`；origin `https://github.com/JunYIChen12/quant-research-live-lab.git`。
- 启动门禁：任务文件、`CURRENT_TASK.md`、`TASKS.md` 均为 `READY_FOR_VERIFY`，责任线程匹配；父级/项目规则、共享/项目工作流、项目状态、任务索引、当前任务、目标任务和 migration 均已独立核对，migration 无未吸收记录。

### 关键发现

1. 有效配置 `leverage` 已在 `src/quant_lab/dry_run.py:1663-1686` 强制解析：缺失和不可解析为 `leverage_invalid`，非 1 为 `leverage_must_be_one`；独立覆盖场景确认缺失、非法和 `2` 均为 `BLOCKED` 且 `/start` 调用次数为 `0`，合法 `1` 为 `RUNNING` 且只调用一次 `/start`。
2. `/start` 不确定响应已在 `src/quant_lab/dry_run.py:1254-1275` 标记 `UNKNOWN` 后读取完整快照；独立顺序检查确认读回顺序包含 `/health`、`/show_config`、`/status`、分页 `/trades`、`/balance`，只调用一次 `/start`。读回不可用时保持 `STARTING`，到 60 秒确认窗口才 `BLOCKED`，未提前终态退出或盲目重放。
3. 关闭核对在 `src/quant_lab/dry_run.py:2099-2167` 保留完整性原因优先级；独立场景确认已有 `loss_lock=True` 时发生 `artifact_hash_mismatch`，最终为 `BLOCKED`，原因保留 `release_integrity` 和完整性错误，`loss_lock` 仍为 `True`。
4. 不确定 `/forceexit` 的独立场景确认第一次异常后，下一次重试前先读完整快照（五个 GET 端点），再发第二次 `/forceexit`；没有在未读回状态前盲目重放。

### 独立验证证据

| 检查 | 实际结果 |
| --- | --- |
| 返工目标四项测试 | `4 passed in 21.28s` |
| `tests/test_dry_run_supervisor.py` | `24 passed in 22.08s` |
| 全量 pytest | `46 passed in 30.17s` |
| Ruff | `All checks passed!` |
| pip check | `No broken requirements found.` |
| compileall | 退出码 `0` |
| `git diff --check` | 退出码 `0` |
| 九类场景与回归 | 相关测试全通过：证据不足、估计达标结算不足、正常达标、到期优先、硬亏损锁、部分平仓重启、用户停止、版本漂移、Codex 不可用；另核对重新授权、参数更新、REST 分页/审计、SQLite 边界 |
| Web 最小结构 | 既有 HTTP/DOM 测试通过，确认本机回环、单页字段、`aria-live` 和无凭据响应；Playwright Python/Node 均不可用，未宣称视觉验收 |
| 敏感信息扫描 | 私钥、AWS、GitHub、Slack、OpenAI key 模式均无匹配；`runtime-password` 仅为测试占位字面量，未读取或生成真实凭据 |

### 失败/跳过项与剩余风险

- 两次独立内存脚本首次调用分别因工作目录相对路径和未关闭临时 SQLite 连接失败；修正调用方式和显式关闭连接后验证通过，均非产品失败。
- 未启动正式 Freqtrade Dry-run 或交易服务，未连接交易所，未下载行情，未读取或生成真实凭据/账户导出；没有真实交易、盈利或实盘授权证据。
- Playwright Python/Node 包不可用；本轮仅保留 HTTP/DOM 结构证据，不覆盖视觉布局验收。
- 工作区仍有其他既有/并行未提交修改，验收未清理、回退、提交或推送；本次只更新本任务文件、`CURRENT_TASK.md` 和 `TASKS.md`。

### 下一责任线程

`00｜项目控制塔`：复核本次独立验收证据，更新稳定项目状态并按工作流决定后续关闭；当前不得由验收线程直接 `CLOSED`。

## 控制塔关闭记录（2026-09-18）

- 控制塔复核第二次独立验收结论和证据后，将任务状态从 `ACCEPTED` 更新为 `CLOSED`；任务单一目标已按约定完成。
- 关闭同步更新 `TASKS.md`、`CURRENT_TASK.md`、`PROJECT_STATE.md` 和归档索引；完整历史继续以本任务文件为唯一事实来源。
- 本次关闭未修改产品代码、测试、策略、配置、发布/安全政策，未清理、回退、提交或推送工作区既有修改。
- 未启动正式 Dry-run、未连接交易所、未读取真实凭据；Playwright 不可用，视觉验收仍未执行。本结论不构成盈利、实盘或发布授权。
- 当前没有经用户确认的后续活动任务；`20260916-004` 保持 `DRAFT`，不自动启动。
