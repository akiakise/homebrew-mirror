# 项目维护约定

## 编码前先拉取

1. 每次开始编码任务，先在仓库根目录执行 `git status --short --branch`，确认当前分支、跟踪分支和未提交改动。
2. 在阅读本次要改的代码前，从当前分支的上游执行 `git pull --ff-only --no-autostash`。成功后以拉取后的文件和项目规则为准，再分析、修改和验证。
3. 没有跟踪分支、无法快进或拉取失败时，先报告原因并等待处理，不在旧基线上继续编码。保留已有改动，不擅自暂存、丢弃或改写分支历史。

## 镜像清单与生成文件

- 增删镜像时，先读 [README.md](README.md) 的「镜像清单」和 [同步脚本](scripts/sync_casks.py) 的 `parse_catalog`。该表是唯一清单，保留 `mirror-catalog:start`、`mirror-catalog:end` 标记与表头。新增行格式为 ``| `example-cask` | 待同步 | 待同步 |``。
- 清单的版本、下载来源和 `Casks/*.rb` 由同步脚本生成。调整生成行为时改脚本；移除镜像时，同时删除对应的 cask 文件，并提醒仓库维护者从 `MIRROR_ALLOWED_CASKS` 移除该名称。
- 调整安装包支持范围时，先核对 Homebrew 上游定义和平台变体。只镜像带固定 SHA-256、使用单个顶层 HTTPS 下载声明的受支持文件格式；遇到不支持的定义或格式时中止，不改写下载地址。保留上游校验和、安装规则和自更新行为。

## 同步与发布

- 修改 [GitHub Actions 工作流](.github/workflows/sync-casks.yml) 时，保留 `main` 推送、UTC+8 午夜定时、手动触发和串行执行。自动回推使用内置 `GITHUB_TOKEN`，并跳过 `github-actions[bot]` 发起的推送，避免循环。
- 修改发布逻辑时，按 [README.md](README.md#自动同步) 约定的日期和架构命名。所有已启用镜像 cask 版本未更新时，只读取上游版本元数据，直接跳过源文件和安装包下载、Release 覆盖及文件写入；检测到版本更新后，才清理当天目标 Release 的附件，先校验所有新包再删除旧附件。上传后核对 GitHub 附件 SHA-256，全部通过才改写 cask 下载地址。
- 修改清单或同步逻辑后，先运行 `python3 -B scripts/sync_casks.py --check` 验证。涉及镜像分支时，用 `MIRROR_ALLOWED_CASKS` 指定本次要检查的 cask。预检只读取上游定义，不下载安装包、不写入文件、不操作 Release；真实发布或覆盖不作为默认验证步骤。
