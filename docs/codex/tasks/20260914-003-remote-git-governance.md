# 20260914-003 远程 Git 仓库治理

## 身份与基线

- 创建日期：2026-09-14，Asia/Shanghai。
- 状态：IN_PROGRESS。
- 当前责任线程：00｜项目控制塔。
- 分析、执行和核对由当前控制塔在同一目标根目录完成；执行后只读核对远程状态。未创建子代理。
- 唯一根目录：D:/CodexProjects/projects/quant-research-live-lab。
- 本地分支：`codex/workbench-init`。
- 写入前 HEAD：`a1de86123465ecbfb17739988826d638c6522e23`。
- 写入前工作区：干净；分支与 `origin/codex/workbench-init` 一致。
- 远程默认分支：`main`；写入前 HEAD：`a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28`。
- 不读取真实交易凭据、账户导出或运行数据；不启动服务，不连接交易所。

## 一个主要目标

治理远程 GitHub 仓库的可见噪音和重复来源，保留项目源代码、测试、必要治理文档、当前需求分支和 Freqtrade 项目功能，不改写 Git 历史。

## 已确认事实

### 远程分支

远程仓库：`JunYIChen12/quant-research-live-lab`。

写入前 `git ls-remote --heads origin` 和 GitHub API 共同确认 6 个远程分支：

- `main`，受保护，当前产品基线为 `a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28`。
- `codex/workbench-init`，当前任务资料分支，HEAD `a1de86123465ecbfb17739988826d638c6522e23`。
- `integration/freqtrade-dry-run`，PR `#7` 的未合并功能分支，HEAD `8d1037fe317ebfddbc3f70b5b306a73ac4681036`。
- `governance/release-integrity-gate`，PR `#5` 已合并，HEAD `70ec3fcc9c38e716808f49b97ff4d3ecbf276929`。
- 三个 Dependabot 分支分别对应 PR `#1`、`#2`、`#3`，只包含单项依赖更新。

### 远程 PR 和项目对象

- PR `#1`、`#2`、`#3` 均为 open、无法合并的 Dependabot 单文件依赖更新，属于本次确认的远程噪音。
- PR `#5` 已 merged 到 `main`，其分支可清理；历史 PR 记录保留。
- PR `#7` open、可合并但尚未合并，包含 Freqtrade Dry-run 项目功能，保留并不关闭。
- Issue `#6` 是 PR `#7` 的项目目标，保留。
- `.github/dependabot.yml` 在 `main` 存在，配置 pip 和 GitHub Actions 每周生成依赖更新；若不处理它，关闭现有 PR 后仍会产生同类噪音。
- 当前 `main` 文件树包含项目源代码、测试、风险和发布文档，以及 `docs/codex` 控制塔记录；这些不是本次清理对象。

## 事实、推断与决定

### 事实

远程有过期依赖 PR、已合并分支和一个仍在持续生成依赖 PR 的配置；同时存在未合并的项目功能分支和当前需求资料分支。

### 推断

本次“只保留项目本身”应解释为清理 GitHub 协作表面的过期对象和重复来源，而不是删除安全规则、发布政策、需求记录或未合并的项目功能。

### 已确认决定

- 关闭 PR `#1`、`#2`、`#3`。
- 删除上述三个 Dependabot 远程分支。
- 删除已经合并的 `governance/release-integrity-gate` 远程分支。
- 通过 `main` 允许的提交流程删除 `.github/dependabot.yml`，并在 `CHANGELOG.md` 记录停用原因：每周依赖 PR 与当前个人项目推进不匹配，造成持续的协作噪音；后续依赖升级改为主动、单项处理。
- 保留 `main`、`codex/workbench-init`、`integration/freqtrade-dry-run`、Issue `#6`、PR `#7` 和历史 PR 记录。
- 不强推、不改写历史、不删除项目代码、不关闭 PR `#7`、不删除 `docs/codex` 资料、不修改安全规则和发布规则。

## 执行顺序

1. 将本任务登记到任务索引和当前指针，并提交、普通推送到 `origin/codex/workbench-init`。
2. 关闭 PR `#1`、`#2`、`#3`。
3. 删除三个 Dependabot 分支及已合并的治理分支。
4. 从当前 `main` 创建一次性治理分支，删除 `.github/dependabot.yml`，在 `CHANGELOG.md` 增加对应记录，提交并创建 PR。
5. 核对该治理 PR 的变更仅限上述两个文件后合并；删除一次性治理分支。
6. 重新读取远程分支、PR、`main` 文件树和当前工作分支，记录最终结果。

## 验收标准

1. 远程不再存在四个已确认待清理分支。
2. PR `#1`、`#2`、`#3` 状态为 closed；PR `#7` 仍为 open；PR `#5` 的历史记录仍为 merged。
3. `main` 不再包含 `.github/dependabot.yml`，且 `CHANGELOG.md` 有停用原因记录。
4. `main`、`codex/workbench-init`、`integration/freqtrade-dry-run`、Issue `#6` 和 PR `#7` 均未被误删或关闭。
5. `main` 治理 PR 不包含项目源代码、测试、安全模型、发布政策或需求资料的删除。
6. 当前本地工作区保持干净；当前需求任务 `20260912-002` 的状态和资料未被错误改写为完成。
7. 远程核对结果、提交 SHA、PR 编号、失败或跳过的检查全部写回本任务文件。

## 回滚

- PR 关闭和分支删除属于远程治理操作；不恢复已确认无用对象，除非发现误删或用户重新授权。
- 停用 Dependabot 的两个文件变更通过新 PR 的 revert 回滚；不移动历史提交，不强推。
- 若 `main` 保护规则不允许按计划合并，记录为 BLOCKED，不绕过保护规则。

## 执行记录

### 登记前核对（2026-09-14）

| 检查 | 结果 |
| --- | --- |
| 当前目录 | `D:/CodexProjects/projects/quant-research-live-lab` |
| 当前分支与 HEAD | `codex/workbench-init` / `a1de86123465ecbfb17739988826d638c6522e23` |
| 工作区 | clean；与 `origin/codex/workbench-init` 一致 |
| 默认分支与 HEAD | `main` / `a5fdc77ccb54f5d4d3d704bf4a78cb0166942c28` |
| 远程分支 | 6 个，详见上文 |
| PR | `#1`、`#2`、`#3` open 且不可合并；`#5` merged；`#7` open 且可合并 |
| 当前任务 | `20260912-002` / `ANALYZING`，本次治理确认后暂挂 |

### 用户授权

2026-09-14 用户确认按推荐方案执行，包括关闭三个 Dependabot PR、删除确认的远程分支和停用 Dependabot 自动 PR。该确认不扩大到删除项目代码、改写历史、关闭 PR `#7` 或修改产品安全规则。

### 尚未执行

登记提交和远程治理动作尚未开始；完成前不得将本任务标记为 ACCEPTED 或 CLOSED。
