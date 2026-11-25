cask "thebrowsercompany-dia" do
  version "1.58.2,91529"
  sha256 "971d8ab2a05e5cbe06e1ebb3397481287f5aa461cd4d5fb1fd8d37afd164796f"

  mirror_download = {
    "971d8ab2a05e5cbe06e1ebb3397481287f5aa461cd4d5fb1fd8d37afd164796f" => ["https://gh-proxy.com/https://github.com/akiakise/homebrew-mirror/releases/download/mirror-thebrowsercompany-dia--1.58.2%2C91529/thebrowsercompany-dia-1-58-2-91529-971d8ab2a05e5cbe-Dia-1.58.2-91529.zip", "Dia-1.58.2-91529.zip"],
  }[sha256.to_s]
  url(mirror_download&.first || "https://releases.diabrowser.com/release/Dia-#{version.tr(",", "-")}.zip")
  rename File.basename(mirror_download.first), mirror_download.last if mirror_download
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
