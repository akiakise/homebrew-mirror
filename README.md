# Homebrew 镜像 Tap

此 Tap 同步 Homebrew 官方的 cask 定义。镜像开启时，每个 cask 的当前版本使用独立的 GitHub Release，并在其中保存该 cask 对应的全部安装包；未开启的项目继续使用上游地址。

## 镜像清单

<!-- mirror-catalog:start -->
| Cask | Homebrew 上游版本 | 下载来源 |
| --- | --- | --- |
| `claude-code` | `2.1.325` | GitHub Releases |
| `thebrowsercompany-dia` | `1.58.1,91403` | GitHub Releases |
| `chatgpt` | `26.1120.50957` | GitHub Releases |
<!-- mirror-catalog:end -->

```sh
brew tap akiakise/mirror
brew install --cask akiakise/mirror/claude-code
brew install --cask akiakise/mirror/thebrowsercompany-dia
brew install --cask akiakise/mirror/chatgpt
```

请用完整名称安装，以选择本 Tap 的同名 cask。镜像仅替换 Homebrew 安装时使用的下载地址，保留上游的校验和、安装规则和应用自更新行为。

## 自动同步

推送到 `main` 时会触发同步，工作流也会在每天北京时间（UTC+8）**00:00** 和 **12:00** 各检查一次 Homebrew 官方 cask。更改配置后，可在 **Actions → 同步 Homebrew 镜像 → Run workflow** 手动运行。GitHub 的定时执行可能延迟。

有变化时，工作流会更新镜像清单和 cask 定义。默认分支须允许工作流推送。

在 **Settings → Secrets and variables → Actions → Variables** 设置下列仓库变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MIRROR_ALLOWED_CASKS` | 空 | 已获再分发授权的 cask 名称，多个用逗号分隔。空值只同步定义，不下载或发布安装包。 |
| `MIRROR_PROXY_PREFIX` | `https://gh-proxy.com/` | 拼接在 GitHub 下载地址前的 HTTPS 前缀。设置为 `direct` 可使用 GitHub 直连；不影响上游地址和 Release 上传。 |

官方 cask 的 BSD 许可不涵盖安装包。请逐项核对 [Claude Code](https://github.com/anthropics/claude-code/blob/main/LICENSE.md)、[Dia](https://www.diabrowser.com/termsofuse) 和 [ChatGPT](https://openai.com/policies/terms-of-use/) 的条款及你取得的授权，再配置 `MIRROR_ALLOWED_CASKS`。三项均获授权时，变量值为 `claude-code,thebrowsercompany-dia,chatgpt`。停用镜像会在下一次同步时恢复该项目的上游链接；清空变量后，同步任务不会操作任何已有 Release。

每个镜像版本使用独立 Release，标签格式为 `mirror-<cask>--<version>`，例如 `mirror-chatgpt--26.1120.50957`。同一个 Release 包含该版本的全部安装包；多包时，附件名会标出平台和架构，例如 `macos-arm64`、`macos-intel`、`linux-arm64`、`linux-intel`。

首次运行新流程时，仍使用日期 Release 的镜像会迁移到各自的版本 Release。迁移后，版本和下载来源未变的 cask 只检查上游版本元数据，不下载上游源文件或安装包，也不操作 Release。只更新一个镜像时，只发布该镜像对应的 Release，不覆盖其他镜像或旧版本的附件。

附件经 GitHub SHA-256 校验后才切换下载链接。若上传或回推失败，可重新触发同步。已发布的 Release 只补传缺失附件，保留现有附件；遇到同名附件校验不匹配时停止，需人工处理。请勿启用不可变发布，否则无法补传附件。

## 历史 Release 清理

独立清理任务每天北京时间（UTC+8）**00:00** 触发，与同步任务串行执行。已发布的镜像 Release 创建满 7 天后，只有在既不对应默认分支的 cask 当前版本、也不被任何 cask 引用时才清理。旧日期 Release 同样受引用保护。删除前如果发现默认分支已变化，任务会停止。只删除 Release 及附件，保留 Git 标签。

## 项目维护

新增或移除镜像、修改同步逻辑及本地验证，见 [AGENTS.md](AGENTS.md)。

源文件来自 [Homebrew/homebrew-cask](https://github.com/Homebrew/homebrew-cask)，许可见 [Casks/LICENSE](Casks/LICENSE)。
