cask "visual-studio-code" do
  arch arm: "darwin-arm64", intel: "darwin"

  on_big_sur :or_older do
    version "1.106.3"
    sha256 arm:   "35dd438808dde1dd1f65490ffe7713ed64102324c0809efbec0b4eb2809b218b",
           intel: "c41872149a205f3a3be3e5d3a8f04920407a0762531e607f78dc93f4d4813cda"

    livecheck do
      skip "Legacy version"
    end
  end
  on_monterey :or_newer do
    version "1.148.0"
    sha256 arm:   "5a6d11ecf8bed45860f81379bc55d1551e561c37076cb4ab8e2c562b3017e183",
           intel: "6fbb0b8ef92530b28c8eb944fc47f129e40305b1913987af2b0e1553ca14ad6b"

    livecheck do
      url "https://update.code.visualstudio.com/api/update/#{arch}/stable/latest"
      strategy :json do |json|
        json["productVersion"]
      end
    end
  end

  mirror_download = {
    "35dd438808dde1dd1f65490ffe7713ed64102324c0809efbec0b4eb2809b218b" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-visual-studio-code--1.148.0/visual-studio-code-1-148-0-macos-arm64-35dd438808dde1dd-stable", "stable"],
    "5a6d11ecf8bed45860f81379bc55d1551e561c37076cb4ab8e2c562b3017e183" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-visual-studio-code--1.148.0/visual-studio-code-1-148-0-macos-arm64-5a6d11ecf8bed458-stable", "stable"],
    "6fbb0b8ef92530b28c8eb944fc47f129e40305b1913987af2b0e1553ca14ad6b" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-visual-studio-code--1.148.0/visual-studio-code-1-148-0-macos-intel-6fbb0b8ef92530b2-stable", "stable"],
    "c41872149a205f3a3be3e5d3a8f04920407a0762531e607f78dc93f4d4813cda" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-visual-studio-code--1.148.0/visual-studio-code-1-148-0-macos-intel-c41872149a205f3a-stable", "stable"],
  }[sha256.to_s]
  url(mirror_download&.first || "https://update.code.visualstudio.com/#{version}/#{arch}/stable")
  rename File.basename(mirror_download.first), mirror_download.last if mirror_download
  name "Microsoft Visual Studio Code"
  name "VS Code"
  desc "Open-source code editor"
  homepage "https://code.visualstudio.com/"

  auto_updates true
  depends_on :macos

  app "Visual Studio Code.app"
  binary "#{appdir}/Visual Studio Code.app/Contents/Resources/app/bin/code"
  binary "#{appdir}/Visual Studio Code.app/Contents/Resources/app/bin/code-tunnel"

  uninstall launchctl: "com.microsoft.VSCode.ShipIt",
            quit:      "com.microsoft.VSCode"

  zap trash: [
    "~/.vscode",
    "~/Library/Application Support/Code",
    "~/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments/com.microsoft.vscode.sfl*",
    "~/Library/Caches/com.microsoft.VSCode",
    "~/Library/Caches/com.microsoft.VSCode.ShipIt",
    "~/Library/HTTPStorages/com.microsoft.VSCode",
    "~/Library/Preferences/ByHost/com.microsoft.VSCode.ShipIt.*.plist",
    "~/Library/Preferences/com.microsoft.VSCode.helper.plist",
    "~/Library/Preferences/com.microsoft.VSCode.plist",
    "~/Library/Saved Application State/com.microsoft.VSCode.savedState",
  ]
end
