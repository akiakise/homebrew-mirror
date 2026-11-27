# 项目维护约定

## 编码前先拉取

1. 每次开始编码任务，先在仓库根目录执行 `git status --short --branch`，确认当前分支、跟踪分支和未提交改动。
2. 在阅读本次要改的代码前，从当前分支的上游执行 `git pull --ff-only --no-autostash`。成功后以拉取后的文件和项目规则为准，再分析、修改和验证。
3. 没有跟踪分支、无法快进或拉取失败时，先报告原因并等待处理，不在旧基线上继续编码。保留已有改动，不擅自暂存、丢弃或改写分支历史。

## 镜像清单与生成文件

- 增删镜像时，编辑唯一清单 [mirror-list.json](mirror-list.json)。新增条目格式为 `"example-cask": {}`；推送前按 README 核对安装包的再分发授权。移除镜像时，同时删除对应的 cask 文件。
- 清单中的 `version`、`state`、`Casks/*.rb` 及 README 的展示表由同步脚本生成。README 表保留 `mirror-catalog:start`、`mirror-catalog:end` 标记，链接指向 Homebrew 仓库对应的 cask 源文件；同步和清理不读取此表作为输入。
- 调整安装包支持范围时，先核对 Homebrew 上游定义和平台变体。只镜像带固定 SHA-256、使用单个顶层 HTTPS 下载声明的受支持文件格式；遇到不支持的定义或格式时中止，不改写下载地址。保留上游校验和、安装规则和自更新行为。

## 同步与发布

- 修改 [GitHub Actions 工作流](.github/workflows/sync-casks.yml) 时，保留 `main` 推送、UTC+8 午夜定时、手动触发和串行执行。自动回推使用内置 `GITHUB_TOKEN`，并跳过 `github-actions[bot]` 发起的推送，避免循环。
- 修改发布逻辑时，沿用 [README.md](README.md#自动同步) 的按 cask、版本和架构命名约定。对同步状态未变的 cask，只读取上游元数据；先校验新包，再清理草稿中的无效附件，已发布 Release 只补传。上传后核对 GitHub 附件 SHA-256，通过后才改写下载地址。
- 修改清理逻辑时，按 Release 对象的创建时间计算保留期，保护默认分支清单的主版本和 cask 的实际下载引用，不删除 Git 标签。
- 修改清单或同步逻辑后，先运行 `python3 -B scripts/sync_casks.py --check` 验证清单全部条目。预检只读取上游定义，不下载安装包、不写入文件、不操作 Release；真实发布或覆盖不作为默认验证步骤。
