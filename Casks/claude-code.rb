cask "claude-code" do
  arch arm: "arm64", intel: "x64"
  os macos: "darwin", linux: "linux"

  version "2.1.326"
  sha256 arm:          "e214ad76dcc0e846b03be28ed1c2734aacd4e27acb527cb7f8a9e2bed644e837",
         intel:        "bd8e26290f93353590b831600a7ced02d625018fbaa2a82d8817368d3e2d2f82",
         arm64_linux:  "98d56f6ffe53469767a74864a38eaf359d62ef557a8de1b1ad524d61a66ec119",
         x86_64_linux: "b6b3647d981130dc44fc670846ae97b6cde531ffb667cf9c4d17cfcafb38cb37"

  mirror_download = {
    "98d56f6ffe53469767a74864a38eaf359d62ef557a8de1b1ad524d61a66ec119" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-claude-code--2.1.326/claude-code-2-1-326-linux-arm64-98d56f6ffe534697-claude", "claude"],
    "b6b3647d981130dc44fc670846ae97b6cde531ffb667cf9c4d17cfcafb38cb37" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-claude-code--2.1.326/claude-code-2-1-326-linux-intel-b6b3647d981130dc-claude", "claude"],
    "bd8e26290f93353590b831600a7ced02d625018fbaa2a82d8817368d3e2d2f82" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-claude-code--2.1.326/claude-code-2-1-326-macos-intel-bd8e26290f933535-claude", "claude"],
    "e214ad76dcc0e846b03be28ed1c2734aacd4e27acb527cb7f8a9e2bed644e837" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-claude-code--2.1.326/claude-code-2-1-326-macos-arm64-e214ad76dcc0e846-claude", "claude"],
  }[sha256.to_s]
  url(mirror_download&.first || "https://downloads.claude.ai/claude-code-releases/#{version}/#{os}-#{arch}/claude")
  rename File.basename(mirror_download.first), mirror_download.last if mirror_download
  name "Claude Code"
  desc "Terminal-based AI coding assistant"
  homepage "https://claude.com/product/claude-code"

  livecheck do
    url "https://downloads.claude.ai/claude-code-releases/stable"
    regex(/^v?(\d+(?:\.\d+)+)$/i)
  end

  conflicts_with cask: "claude-code@latest"

  binary "claude"

  zap trash: [
        "~/.cache/claude",
        "~/.claude.json*",
        "~/.config/claude",
        "~/.local/bin/claude",
        "~/.local/share/claude",
        "~/.local/state/claude",
        "~/Library/Caches/claude-cli-nodejs",
      ],
      rmdir: "~/.claude"
end
