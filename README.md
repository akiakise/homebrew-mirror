# Homebrew 镜像 Tap

此 Tap 同步 Homebrew 官方的 cask 定义。安装包镜像开启后，下载地址指向本仓库的 GitHub Releases；否则保留上游地址。

## 镜像清单

<!-- mirror-catalog:start -->
| Cask | Homebrew 上游版本 | 下载来源 |
| --- | --- | --- |
| `claude-code` | `2.1.323` | 上游直连 |
| `thebrowsercompany-dia` | `1.58.1,91403` | 上游直连 |
| `chatgpt` | `26.1117.41037` | 上游直连 |
<!-- mirror-catalog:end -->

```sh
brew tap akiakise/mirror
brew install --cask akiakise/mirror/claude-code
brew install --cask akiakise/mirror/thebrowsercompany-dia
brew install --cask akiakise/mirror/chatgpt
```

请用完整名称安装，以选择本 Tap 的同名 cask。镜像仅替换 Homebrew 安装时使用的下载地址，保留上游的校验和、安装规则和应用自更新行为。

## 自动同步

工作流推送到默认分支后，GitHub Actions 每天北京时间 **00:00（UTC+8）** 检查 Homebrew 官方 cask。首次启用或更改配置后，也可在 **Actions → 同步 Homebrew 镜像 → Run workflow** 手动运行。有变化时才提交 README 和 cask 文件；默认分支须允许该工作流推送。GitHub 的定时执行可能延迟。

在 **Settings → Secrets and variables → Actions → Variables** 设置下列仓库变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MIRROR_ALLOWED_CASKS` | 空 | 已获再分发授权的 cask 名称，多个用逗号分隔。空值只同步定义，不下载或发布安装包。 |
| `MIRROR_PROXY_PREFIX` | `https://gh-proxy.com/` | 拼接在 GitHub 下载地址前的 HTTPS 前缀。设置为 `direct` 可使用 GitHub 直连；不影响上游地址和 Release 上传。 |

官方 cask 的 BSD 许可不涵盖安装包。请逐项核对 [Claude Code](https://github.com/anthropics/claude-code/blob/main/LICENSE.md)、[Dia](https://www.diabrowser.com/termsofuse) 和 [ChatGPT](https://openai.com/policies/terms-of-use/) 的条款及你取得的授权，再配置 `MIRROR_ALLOWED_CASKS`。三项均获授权时，变量值为 `claude-code,thebrowsercompany-dia,chatgpt`。停用镜像会在下一次同步时恢复上游链接，不会删除已发布的 Release。

安装包作为版本化 Release 附件保存，不写入 Git 历史。同步先按 Homebrew 官方 SHA-256 校验原包，再核对 GitHub 返回的附件摘要；全部通过才更新 cask 下载地址。相同版本和内容的附件会复用；已发布的附件不会被覆盖。校验或上传失败时工作流不会推送 cask 更新。

## 维护清单

在上表标记内新增一行，例如 ``| `example-cask` | 待同步 | 待同步 |``。版本和下载来源由同步脚本填写。移除时同时删除对应的 `Casks/<名称>.rb`，以及 `MIRROR_ALLOWED_CASKS` 中的名称。安装包镜像要求上游发布固定 SHA-256，并使用单个顶层 HTTPS 下载地址；遇到不支持的定义会报错，不改写下载地址。

本地运行 `python3 -B scripts/sync_casks.py --check` 可检查上游定义及配置，不写入文件、不下载或上传安装包。源文件来自 [Homebrew/homebrew-cask](https://github.com/Homebrew/homebrew-cask)，许可见 [Casks/LICENSE](Casks/LICENSE)。
