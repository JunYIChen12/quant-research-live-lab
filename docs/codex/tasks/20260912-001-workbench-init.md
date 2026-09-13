# 20260912-001 项目工作台初始化

## 身份与基线

- 日期：2026-09-12，Asia/Shanghai。
- 状态：CLOSED；当前责任线程：00｜项目控制塔（关闭记录负责人）。
- 唯一根目录：D:/CodexProjects/projects/quant-research-live-lab。
- 初始分支 main，初始工作区干净；任务分支 codex/workbench-init。
- HEAD：a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28。
- origin fetch/push：https://github.com/JunYIChen12/quant-research-live-lab.git。
- Windows，PowerShell 7.6.5；Python 与依赖安装状态未核验。

## 目标与来源

用户确认开展工作台初始化。新线程应仅凭仓库找到规则、项目事实、唯一任务、负责人、修改边界和验收方法，无需聊天保存唯一事实。

## 已确认事实

- 已读取父级 D:/CodexProjects/AGENTS.md、项目 AGENTS.md、共享 D:/CodexProjects/docs/codex/WORKFLOW.md。D:/AGENTS.md 与 D:/CodexProjects/projects/AGENTS.md 不存在。
- 启动时项目 docs/codex 下 WORKFLOW.md、PROJECT_STATE.md、TASKS.md、CURRENT_TASK.md、migration/ 和 tasks/ 的 Test-Path 结果均为 False。
- 已读 README.md、CONTRIBUTING.md、pyproject.toml、.github/workflows/ci.yml、docs/architecture.md、docs/safety-model.md、docs/governance/GOVERNANCE.md、docs/governance/RELEASE_POLICY.md。
- 配置声明 Python >=3.12，无生产依赖；开发依赖 pytest 和 ruff。CI 配置安装 .[dev] 后执行 ruff check . 和 pytest，不能据此声称实际通过。
- README 路线图不自动转为已确认任务。

## 修改范围

仅允许：docs/codex/WORKFLOW.md、PROJECT_STATE.md、TASKS.md、CURRENT_TASK.md、tasks/20260912-001-workbench-init.md，以及 decisions/README.md、migration/README.md、archive/README.md；AGENTS.md 只追加流程引用；CHANGELOG.md 记录落地原因。

初始控制塔仅登记三个任务文件。用户随后要求“你帮我实现吧”，本次文档实施由当前线程接管，独立验收仍须另行进行；此为本任务角色安排，不修改稳定角色规则。目录说明不冒充历史交接。不得修改父级共享文件。

## 保持不变与范围外

原八条安全规则原文保留。产品代码、测试、依赖、CI、配置、治理发布政策、环境、网络、凭据及数据不变。不读取真实凭据或账户导出。不提交、推送、部署，不开发业务，不新增实盘适配器，不清理旧资源。

## 验收标准

1. 工作流入口和项目状态齐全，tasks/、decisions/、migration/、archive/ 可跟踪，所有引用可解析。
2. 只有本任务；索引、指针、任务文件的编号、状态、责任归属一致。
3. 项目状态区分已核对事实、文档声明、推断及 UNKNOWN，不声称运行或测试通过。
4. 原安全规则逐字保留；CHANGELOG.md 说明工作台缺失造成重复启动核对及交接事实不能落库的问题。尚无本项目重复事故证据，不得编造。
5. 差异仅在白名单；空白检查覆盖新增文件；无敏感信息或业务改动。
6. 有自测证据、跳过项、回退说明；独立验收前不能 ACCEPTED/CLOSED。

## 验证方法

按新线程启动顺序回读文档，检查 Markdown 标题、表格与路径；Test-Path 检查链接；git status --short 和 git diff 检查范围，git diff --check 检查跟踪文件。新增文件另行回读与空白检查，不能凭普通 diff 为空判断通过。使用 git show a5fdc77:AGENTS.md 核对原规则。文档任务不安装依赖或运行业务测试，明确记录未执行项。

## 分析证据与决定

事实：git status --short --branch 初始仅显示 main...origin/main；git rev-parse HEAD 返回上述 SHA；git remote -v 返回上述 origin；$PSVersionTable.PSVersion.ToString() 返回 7.6.5；git switch -c codex/workbench-init 成功。未 fetch，远程实时状态未知。

推断：现有共享规范足够，不需要新增分析线程。决定：控制塔此前完成 DRAFT -> ANALYZING -> READY 的边界与验收核对；这是历史流转，当前状态见文件顶部。

## 实施摘要与自测

已建立项目流程入口、项目状态、三个记录目录说明和 CHANGELOG.md，并只向 AGENTS.md 追加入口；保留控制塔三个任务文件。共涉及白名单内 10 个文件，未修改产品或运行环境。

2026-09-12 自测：按启动顺序回读入口和状态文件，目标、白名单、负责人和下一步均可直接定位；Markdown 标题与表格源文检查通过。PowerShell 检查 10 个文件的本地链接、行尾空白、AGENTS 原文前缀和差异范围，输出 PASS；git diff --check 退出 0。新增文件也单独检查，不将普通 diff 为空当作通过。内容回读未发现敏感信息或调试残留。

可在项目根目录复跑的最终检查（PowerShell 7）：

```powershell
$ErrorActionPreference = 'Stop'
$allowed = @('AGENTS.md','CHANGELOG.md','docs/codex/WORKFLOW.md','docs/codex/PROJECT_STATE.md','docs/codex/TASKS.md','docs/codex/CURRENT_TASK.md','docs/codex/tasks/20260912-001-workbench-init.md','docs/codex/decisions/README.md','docs/codex/migration/README.md','docs/codex/archive/README.md')
foreach ($f in $allowed) {
    $text = Get-Content -LiteralPath $f -Raw
    if ($text -match '(?m)[ \t]+$') { throw "Whitespace: $f" }
    foreach ($m in [regex]::Matches($text, '\]\(([^)]+)\)')) {
        $target = $m.Groups[1].Value
        if ($target -notmatch '^https?://' -and -not (Test-Path -LiteralPath (Join-Path (Split-Path (Join-Path (Get-Location) $f)) $target))) { throw "Link: $f" }
    }
}
$old = @(git show a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28:AGENTS.md)
if ($LASTEXITCODE -ne 0) { throw 'Git baseline read failed' }
$now = @(Get-Content AGENTS.md)
if (Compare-Object $old $now[0..($old.Count-1)] -SyncWindow 0) { throw 'Original rules changed' }
$changed = @(git diff --name-only HEAD)
if ($LASTEXITCODE -ne 0) { throw 'Git diff failed' }
$changed += @(git ls-files --others --exclude-standard)
if ($LASTEXITCODE -ne 0) { throw 'Git listing failed' }
foreach ($f in $changed) { if ($f -notin $allowed) { throw "Scope: $f" } }
foreach ($f in $allowed[4..6]) { if ((Get-Content $f -Raw) -notmatch 'READY_FOR_VERIFY') { throw "State: $f" } }
git diff --check HEAD
if ($LASTEXITCODE -ne 0) { throw 'Git whitespace check failed' }
'PASS: 10 files; links, whitespace, original rules, scope, state'
```

未执行：业务 pytest/ruff、依赖安装、远程 CI 与分支保护、浏览器 Markdown 渲染及现场验证。仅回读 Markdown 源文，不冒充浏览器视觉验收；文档自测不能证明业务正确性。未提交、推送或部署。

此前登记阶段补丁工具首次管道调用因要求 UTF-8 参数失败，第二次经 bat 传参因结束行解析失败，均未写文件；检查包装器后改用其指向的 codex.exe 直接传参成功。

## 独立验收

2026-09-12 接管：30｜验收｜20260912-001 项目工作台初始化已按用户指令独立接管；来源任务 01a09416-4080-7b41-a5bc-a56dae7cf247。Get-Location、git status --short --branch、git rev-parse HEAD 实测为本文件唯一根目录、codex/workbench-init、a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28；三处状态均 READY_FOR_VERIFY。用户交接声明控制塔停止写入；未自行探查其他任务进程。接管保持 READY_FOR_VERIFY，仅更新本文件及 CURRENT_TASK.md 的责任与接管记录。验收证据和最终状态仅允许写入 TASKS.md、CURRENT_TASK.md 和本文件；不修复、不提交。

## 风险与下一步

当前下一步：控制塔已接管并关闭，等待用户需求。以下实施、验收交接段落及自测脚本为历史证据，其中阶段状态断言不适用于 CLOSED；关闭结果见文末，不覆盖原验收结论。

2026-09-12 用户授权当前线程实施，已回读任务与基线并接管，历史流转 READY -> IN_PROGRESS -> READY_FOR_VERIFY。没有启动其他写入线程。下一步创建独立验收线程并明确接管责任；未 ACCEPTED 或 CLOSED。父工作区共享规范是本地外部依赖，换机须恢复；运行环境、依赖、CI、远程保护和现场状态未核验。

回退仅用经审阅的反向补丁撤销本任务内容，保留用户修改及原规则，不自动删除目录或执行破坏性 Git 操作。

## 独立验收结果与证据（2026-09-12）

结论：ACCEPTED，仅接受本地文档工作台初始化。新验收线程已实际依次从 AGENTS 入口找到工作流、项目状态、索引、指针、唯一任务和 migration 说明，并在无需补问实施线程的情况下定位目标、边界、责任和验收方法。没有发现需返工的问题，不代表产品正确、远程批准、运行可用或实盘授权。

### 独立回读

- 已完整回读父级与项目 AGENTS、共享与项目 WORKFLOW、四个项目入口记录、唯一任务、CHANGELOG 和三个目录 README；docs 下无更深层 AGENTS。migration 只有 README，无可吸收记录；tasks 只有本任务。目录占位没有冒充历史迁移或关闭事实。
- 人工核对 Markdown 标题、表格、链接及围栏源文；索引只包含编号、标题、状态和路径。接管前编号和 READY_FOR_VERIFY 一致，责任均为控制塔；接管后两处责任均为 30。交付状态同步为 ACCEPTED，下一步是控制塔，不越权 CLOSED。
- 回读 README、CONTRIBUTING、pyproject.toml、CI、architecture、safety-model、GOVERNANCE、RELEASE_POLICY，与 PROJECT_STATE 的静态声明逐项对照。Python >=3.12、空生产依赖、pytest/ruff/hatchling 和 CI 命令来源匹配；所列两个产品文件和两个测试文件 Test-Path 均 True，仅证明存在。
- CHANGELOG 第 8 行明确依据为原工作台缺失，明确没有本项目重复事故证据；没有将一般交接风险写成已发生事故。原目录缺失、初始干净 main 和历史 READY 流转属于实施记录，本轮不能追溯证明，不把它们作为现场实测结论。
- 全部 10 个待验收文档已人工回读，未见真实凭据、账户导出、业务实现、调试残留或意外内容；未扫描真实数据存储。回退说明限定为审阅后的反向补丁、保留用户内容和原规则，无自动删除或破坏性 Git 操作；没有执行回退演练。

### 命令与实际结果

执行环境始终为唯一项目目录、Windows / PowerShell 7.6.5；没有切换项目或 worktree。

| 命令或检查 | 实际结果 |
| --- | --- |
| Get-Location；git rev-parse --show-toplevel | D:/CodexProjects/projects/quant-research-live-lab |
| git status --short --branch；git rev-parse HEAD | codex/workbench-init；a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28 |
| git remote -v；$PSVersionTable.PSVersion.ToString() | origin fetch/push 与基线一致；7.6.5；未 fetch |
| git diff HEAD -- AGENTS.md | 仅追加 4 行流程入口，无删除 |
| git diff --name-only HEAD 加 git ls-files --others --exclude-standard，与完整白名单双向 Compare-Object | PASS exact changed file set: 10；包含未跟踪文件，不仅看 diff |
| git diff --cached --name-only | 无输出，退出 0，无暂存变更 |
| git status --porcelain=v1 --untracked-files=all | 1 个已跟踪修改 AGENTS.md，9 个未跟踪文档，无白名单外变更 |
| Get-ChildItem docs/codex -Recurse -File | 8 个工作台文件；三个记录目录与任务路径存在 |
| git show HEAD:AGENTS.md；Compare-Object -CaseSensitive -SyncWindow 0 对比完整原文前缀；统计 ^[1-8] 条款 | PASS original complete AGENTS prefix and eight rules, case-sensitive |
| 逐文件 UTF8 严格解码、空白/冲突标记/围栏/本地链接独立检查 | PASS UTF8, nonempty, whitespace, conflict markers, fences; local links=26 |
| git diff --check HEAD | 退出 0；PASS，新增文件另行检查 |

独立检查没有执行文档中嵌入的自测脚本，而是自行构造精确文件集合及逐文件检查：使用任务内 $allowed 完整 10 路径，Compare-Object 比较排序后的双向集合；[IO.File]::ReadAllText 配合 [Text.UTF8Encoding]::new($false,$true) 拒绝无效 UTF8；拒绝空文件、行尾空格或制表符、NUL、替换字符、合并冲突标记、缺失末尾换行及额外空白尾行。逐行切换三反引号围栏状态，围栏外 Markdown 链接按所属文档目录 Join-Path 后 GetFullPath、Test-Path 验证；本地目标共 26 个，父共享入口解析至 D:/CodexProjects/docs/codex/WORKFLOW.md。三处当前状态单独检查，不将任务历史中的状态字符串当作当前状态证据。检查退出码为 0。

### 保留对象指纹

在写入最终验收状态前，用 Get-FileHash -Algorithm SHA256 记录 7 个不允许验收修改的待验收文件；最终回读须与以下值相同：

```text
AGENTS.md 298C902BDCD158323F96B370440D4C90B701C2E6D60DE204895556C0DC7C03F5
CHANGELOG.md A6EC2F8B86EA4E851682C8613B231611CF30385ECA8A13C1EEC3B6166707F7BE
docs/codex/WORKFLOW.md 6C9ABB70A7D2E1FF8F59DC8221DB4B0C1497F3D050E15A34854B129150D2A19C
docs/codex/PROJECT_STATE.md 277AA6E464AA90070EDE64A42BE6FBB6A8B93158AD058CDC6D5D7C753DEE771F
docs/codex/decisions/README.md 2868571E0596A6F46EA69291D0DF8730FCA29EE10835A3623E0C9DC345D6DDA5
docs/codex/migration/README.md E3479B98E877DB7C01CA34AABDB9886208D811DB2E797221D16CC266D33E47B6
docs/codex/archive/README.md 8E234E0899253972EEDCC7C587D6D9841FF78D6371223A939C735F5B9E1768C2
```

### 跳过、限制与交还

最终回读已执行：从本节指纹表提取 7 条路径/SHA256 并逐个 Get-FileHash 比较，输出 PASS preserved SHA256: 7/7；按索引任务行及两处行首状态字段提取，三处均 ACCEPTED，责任和下一线程一致；最终 10 文件空白检查 PASS，git diff --check HEAD 退出 0。git status --short --branch --untracked-files=all 仍为同一 10 文件集合，git rev-parse HEAD 未变。未修改任何保留对象。

未运行 pytest/ruff、安装依赖、检查远程 CI 或分支保护、浏览器 Markdown 渲染、进程/存储隔离/现场验证；这些保持 UNKNOWN 或未执行。验收仅检查 Markdown 源文结构与路径，不声称浏览器视觉通过。共享规范依赖父目录，换机仍需恢复该文件。未读取真实凭据或账户导出，未连接交易所，未改环境、产品、父目录或 PROJECT_STATE.md，未清理、暂存、提交、推送、部署或关闭任务。

本验收实际写入仅 TASKS.md、CURRENT_TASK.md、本任务文件；无范围偏离。下一步交还 00｜项目控制塔复核本节与未提交差异后决定关闭，不能自动开展业务开发或解释为发布授权。

## 控制塔关闭（2026-09-12）

控制塔接收独立验收任务 01a09439-21e4-7573-b043-d775b87eaa07 的完成结果，实时确认其已完成且 idle；回读仓库三处 ACCEPTED 状态和完整验收证据后接管。git rev-parse HEAD 仍为本文件基线，git status --short --branch 仍为 codex/workbench-init 和文档修改，AGENTS diff 仅追加入口。

关闭前从上述指纹表读取七条 SHA256，以 Get-FileHash 逐项核对，输出 PASS acceptance fingerprints 7/7；git diff --check HEAD 退出 0。据此确认验收后的保留对象未变化，无待处理返工。决定 ACCEPTED -> CLOSED，仅限文档工作台初始化。

关闭写入：TASKS.md、CURRENT_TASK.md、本文件、PROJECT_STATE.md、archive/README.md。项目状态沉淀验收范围与未提交限制；当前指针恢复“当前无活动任务”；归档目录链接原任务而不复制证据。PROJECT_STATE 和 archive 说明在关闭后会改变，七项指纹是关闭前验收证据，不是永久不变断言。

关闭后核对文件链接、空白、索引与任务顶部 CLOSED、当前无活动任务、10 文件白名单及 git diff --check HEAD。业务测试、远程、浏览器渲染及现场仍未验证；未提交、推送、合并或部署，后续 Git 持久化须另获授权。无新业务任务，验收任务可归档但本轮不自动归档。
