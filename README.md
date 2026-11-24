# Homebrew 镜像 Tap

此 Tap 同步 Homebrew 官方的 cask 定义。镜像开启时，一次同步的全部安装包放在同一个 GitHub Release；未开启的项目继续使用上游地址。

## 镜像清单

<!-- mirror-catalog:start -->
| Cask | Homebrew 上游版本 | 下载来源 |
| --- | --- | --- |
| `claude-code` | `2.1.325` | GitHub Releases |
| `thebrowsercompany-dia` | `1.58.1,91403` | GitHub Releases |
| `chatgpt` | `26.1120.41243` | GitHub Releases |
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

官方 cask 的 BSD 许可不涵盖安装包。请逐项核对 [Claude Code](https://github.com/anthropics/claude-code/blob/main/LICENSE.md)、[Dia](https://www.diabrowser.com/termsofuse) 和 [ChatGPT](https://openai.com/policies/terms-of-use/) 的条款及你取得的授权，再配置 `MIRROR_ALLOWED_CASKS`。三项均获授权时，变量值为 `claude-code,thebrowsercompany-dia,chatgpt`。停用镜像会在下一次同步时恢复该项目的上游链接；清空变量时不会操作任何已有 Release。

Release 按同步开始时的北京时间（UTC+8）归档，例如标签 `mirror-2026-11-23`、标题「Homebrew 镜像 2026-11-23」。同一天的同步使用同一个 Release，不受触发提交影响。一个 cask 有多个安装包时，附件名会标出平台与架构，例如 `macos-arm64`、`macos-intel`、`linux-arm64`、`linux-intel`，以区分同一软件版本的不同包。

如果所有已启用镜像 cask 的上游版本都没有变化，工作流只读取上游版本元数据后直接跳过，不下载上游源文件和安装包、不覆盖 Release，也不写入 README 或 cask 文件。同日只有检测到至少一个已启用镜像 cask 版本更新时，才会覆盖当天的安装包；历史 Release 不受影响。

覆盖期间，下载链接可能暂时不可用；被替换版本的旧链接会失效。若上传失败，可重新触发同步。请勿启用不可变发布，否则无法覆盖当天的附件。

## 项目维护

新增或移除镜像、修改同步逻辑及本地验证，见 [AGENTS.md](AGENTS.md)。

源文件来自 [Homebrew/homebrew-cask](https://github.com/Homebrew/homebrew-cask)，许可见 [Casks/LICENSE](Casks/LICENSE)。
