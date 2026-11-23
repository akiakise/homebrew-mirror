cask "chatgpt" do
  arch arm: "arm64", intel: "x64"
  livecheck_arch = on_arch_conditional intel: "-x64"

  version "26.1117.41037"
  sha256 arm:   "bc0a42d01a9bdede1c1c2b876151a818560d6b1eaf1f45ae402d3d2229c34220",
         intel: "72617c861a86f3e2aba7f60422bb0cf793a7a3969a387de52e6a685d3e970d4f"

  mirror_download = {
    "72617c861a86f3e2aba7f60422bb0cf793a7a3969a387de52e6a685d3e970d4f" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-8a289c319d72cbea18607736570512024a37465b/chatgpt-26-1117-41037-72617c861a86f3e2-ChatGPT-darwin-x64-26.1117.41037.zip", "ChatGPT-darwin-x64-26.1117.41037.zip"],
    "bc0a42d01a9bdede1c1c2b876151a818560d6b1eaf1f45ae402d3d2229c34220" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-8a289c319d72cbea18607736570512024a37465b/chatgpt-26-1117-41037-bc0a42d01a9bdede-ChatGPT-darwin-arm64-26.1117.41037.zip", "ChatGPT-darwin-arm64-26.1117.41037.zip"],
  }[sha256.to_s]
  url(mirror_download&.first || "https://persistent.oaistatic.com/codex-app-prod/ChatGPT-darwin-#{arch}-#{version}.zip")
  rename File.basename(mirror_download.first), mirror_download.last if mirror_download
  name "ChatGPT"
  desc "OpenAI's official ChatGPT desktop app"
  homepage "https://chatgpt.com/"

  livecheck do
    url "https://persistent.oaistatic.com/codex-app-prod/appcast#{livecheck_arch}.xml"
    strategy :sparkle, &:short_version
  end

  auto_updates true
  depends_on macos: :ventura

  app "ChatGPT.app"

  uninstall quit: "com.openai.codex"

  zap trash: [
        "/Library/Application Support/CodexComputerUseAuthorizationPlugin",
        "~/Library/Application Scripts/*.com.openai.sky.CUAService",
        "~/Library/Application Support/Codex",
        "~/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments/com.openai.codex.sfl*",
        "~/Library/Application Support/com.openai.codex",
        "~/Library/Application Support/OpenAI/Codex",
        "~/Library/Caches/Codex",
        "~/Library/Caches/com.openai.codex",
        "~/Library/Caches/com.openai.sky.CUAService",
        "~/Library/Group Containers/*.com.openai.sky.CUAService",
        "~/Library/HTTPStorages/com.openai.codex",
        "~/Library/HTTPStorages/com.openai.codex.binarycookies",
        "~/Library/HTTPStorages/com.openai.sky.CUAService",
        "~/Library/HTTPStorages/com.openai.sky.CUAService.binarycookies",
        "~/Library/Logs/com.openai.codex",
        "~/Library/Preferences/com.openai.codex.plist",
        "~/Library/Preferences/com.openai.sky.CUAService.cli.plist",
        "~/Library/Preferences/com.openai.sky.CUAService.plist",
        "~/Library/Saved Application State/com.openai.codex.savedState",
      ],
      rmdir: "~/.codex"
end
