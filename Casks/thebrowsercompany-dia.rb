cask "thebrowsercompany-dia" do
  version "1.58.1,91403"
  sha256 "738346f55d1a595061c5609ebe68a64c387e52ed7971106ec7ec8adefc1bb765"

  url({
    "738346f55d1a595061c5609ebe68a64c387e52ed7971106ec7ec8adefc1bb765" => "https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-thebrowsercompany-dia-1.58.1-91403-fb1fb297be8b952a/Dia-1.58.1-91403.zip",
  }.fetch(sha256.to_s) { "https://releases.diabrowser.com/release/Dia-#{version.tr(",", "-")}.zip" })
  name "Dia"
  desc "Web browser"
  homepage "https://www.diabrowser.com/"

  livecheck do
    url "https://releases.diabrowser.com/BoostBrowser-updates.xml"
    strategy :sparkle
  end

  auto_updates true
  depends_on arch: :arm64
  depends_on macos: :sonoma

  app "Dia.app"

  zap trash: [
    "~/Library/Application Support/Dia",
    "~/Library/Caches/company.thebrowser.dia",
    "~/Library/Caches/Dia",
    "~/Library/HttpStorages/company.thebrowser.dia",
    "~/Library/HttpStorages/company.thebrowser.dia.binarycookies",
    "~/Library/Preferences/company.thebrowser.dia.plist",
  ]
end
