# Homebrew 镜像 Tap

此 Tap 同步 [mirror-list.json](mirror-list.json) 中的 Homebrew 官方 cask，并默认将安装包镜像到 GitHub Releases。

## 镜像清单

下表由同步任务生成，仅供查看。点击 cask 名称可直接打开上游 Homebrew 仓库里的 cask 源文件。

<!-- mirror-catalog:start -->
| Cask | Homebrew 上游版本 | 下载来源 |
| --- | --- | --- |
| [`claude-code`](https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/c/claude-code.rb) | `2.1.326` | GitHub Releases |
| [`thebrowsercompany-dia`](https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/t/thebrowsercompany-dia.rb) | `1.58.2,91529` | GitHub Releases |
| [`chatgpt`](https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/c/chatgpt.rb) | `26.1120.50957` | GitHub Releases |
| [`visual-studio-code`](https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/v/visual-studio-code.rb) | `1.148.0` | GitHub Releases |
<!-- mirror-catalog:end -->

```sh
brew tap akiakise/mirror
brew install --cask akiakise/mirror/claude-code
brew install --cask akiakise/mirror/thebrowsercompany-dia
brew install --cask akiakise/mirror/chatgpt
brew install --cask akiakise/mirror/visual-studio-code
```

请用完整名称安装，以选择本 Tap 的同名 cask；标记为「待同步」的项目须等首次同步完成后才能从本 Tap 安装。镜像仅替换 Homebrew 安装时使用的下载地址，保留上游的校验和、安装规则和应用自更新行为。

## 自动同步

推送到 `main` 时会触发同步，工作流也会在每天北京时间（UTC+8）**00:00** 和 **12:00** 各检查一次 Homebrew 官方 cask。更改配置后，可在 **Actions → 同步 Homebrew 镜像 → Run workflow** 手动运行。GitHub 的定时执行可能延迟。

有变化时，工作流会回写 `mirror-list.json` 的版本和同步状态，并更新 cask 定义与 README 展示表。默认分支须允许工作流推送。

在 **Settings → Secrets and variables → Actions → Variables** 设置下列仓库变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MIRROR_PROXY_PREFIX` | `https://gh-proxy.com/` | 拼接在 GitHub 下载地址前的 HTTPS 前缀。设置为 `direct` 可使用 GitHub 直连；不影响上游地址和 Release 上传。 |

官方 cask 的 BSD 许可不涵盖安装包。推送清单前，请逐项核对安装包的再分发授权：[Claude Code](https://github.com/anthropics/claude-code/blob/main/LICENSE.md)、[Dia](https://www.diabrowser.com/termsofuse)、[ChatGPT](https://openai.com/policies/terms-of-use/) 和 [Visual Studio Code](https://code.visualstudio.com/license)。微软的标准产品许可不允许分享或发布其 VS Code 安装包；仅在另获再分发授权后，才能将该条目推送到会自动发布的 `main`。

每个 cask 按 Homebrew 主版本使用独立 Release，标签格式为 `mirror-<cask>--<version>`，例如 `mirror-chatgpt--26.1120.50957`。同一个 Release 包含各受支持平台的安装包，包括上游为旧版系统保留的版本；多包时，附件名会标出平台和架构，例如 `macos-arm64`、`macos-intel`、`linux-arm64`、`linux-intel`。

首次同步会记录上游定义和各平台安装包的状态，并将仍使用日期 Release 的镜像迁移到各自的版本 Release。后续对已记录且未变化的 cask，只读取上游元数据，不下载源文件或安装包，也不操作 Release。只更新一个镜像时，只发布该镜像对应的 Release，不覆盖其他镜像或旧版本的附件。

附件经 GitHub SHA-256 校验后才切换下载链接。若上传或回推失败，可重新触发同步。已发布的 Release 只补传缺失附件，保留现有附件；遇到同名附件校验不匹配时停止，需人工处理。请勿启用不可变发布，否则无法补传附件。

## 历史 Release 清理

独立清理任务每天北京时间（UTC+8）**00:00** 触发，与同步任务串行执行。已发布的镜像 Release 创建满 7 天后，只有在既不对应默认分支清单的主版本、也不被任何 cask 引用时才清理。旧日期 Release 同样受引用保护。删除前如果发现默认分支已变化，任务会停止。只删除 Release 及附件，保留 Git 标签。

## 项目维护

新增或移除镜像、修改同步逻辑及本地验证，见 [AGENTS.md](AGENTS.md)。

源文件来自 [Homebrew/homebrew-cask](https://github.com/Homebrew/homebrew-cask)，许可见 [Casks/LICENSE](Casks/LICENSE)。
