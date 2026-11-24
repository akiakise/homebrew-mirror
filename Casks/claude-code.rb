cask "claude-code" do
  arch arm: "arm64", intel: "x64"
  os macos: "darwin", linux: "linux"

  version "2.1.325"
  sha256 arm:          "84590fefe6338be9087f5814b61f9a54c5f21524163a4c127cb5a808e31009f2",
         intel:        "af9760c59f947044e2a0d5072343de563f31efb68bd18ccee4f43c5240570de7",
         arm64_linux:  "7b6e484b1989a5a14a4b354709ccc8672518a3ec5b9ccd7981fc6254327fde67",
         x86_64_linux: "0dc4f4a9a165fc60746d7ae8489712e5fc352f1e7ad4eb22e7141bd0812eb0cf"

  mirror_download = {
    "0dc4f4a9a165fc60746d7ae8489712e5fc352f1e7ad4eb22e7141bd0812eb0cf" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-2026-11-24/claude-code-2-1-325-linux-intel-0dc4f4a9a165fc60-claude", "claude"],
    "7b6e484b1989a5a14a4b354709ccc8672518a3ec5b9ccd7981fc6254327fde67" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-2026-11-24/claude-code-2-1-325-linux-arm64-7b6e484b1989a5a1-claude", "claude"],
    "84590fefe6338be9087f5814b61f9a54c5f21524163a4c127cb5a808e31009f2" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-2026-11-24/claude-code-2-1-325-macos-arm64-84590fefe6338be9-claude", "claude"],
    "af9760c59f947044e2a0d5072343de563f31efb68bd18ccee4f43c5240570de7" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-2026-11-24/claude-code-2-1-325-macos-intel-af9760c59f947044-claude", "claude"],
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
