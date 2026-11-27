import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from selectors import DefaultSelector, EVENT_READ
import subprocess
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MIRROR_LIST = "mirror-list.json"
CATALOG_START = "<!-- mirror-catalog:start -->"
CATALOG_END = "<!-- mirror-catalog:end -->"
TABLE_HEADER = "| Cask | Homebrew 上游版本 | 下载来源 |\n| --- | --- | --- |"
TOKEN_PATTERN = r"[a-z0-9]+(?:[-@+.][a-z0-9]+)*"
VERSION_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._,+-]*"
SHA256_PATTERN = r"[0-9a-f]{64}"
URL_STANZA = re.compile(r'^  url ("(?:[^"\\#\n]|\\[^\n]|#\{[^{}\n]+\})+")$', re.MULTILINE)
VERSION_STANZA = re.compile(r'^ {2,}version (?:"([^"\n]+)"|:(latest))$', re.MULTILINE)
CASK_API = "https://formulae.brew.sh/api/cask"
CASK_SOURCE_PAGE = "https://github.com/Homebrew/homebrew-cask/blob/HEAD"
UPSTREAM_RAW = "https://raw.githubusercontent.com/Homebrew/homebrew-cask"
DEFAULT_PROXY = "https://gh-proxy.com/"
MIRROR_TAG_PREFIX = "mirror-"
VERSIONED_TAG = re.compile(rf"{MIRROR_TAG_PREFIX}{TOKEN_PATTERN}--{VERSION_PATTERN}")
UTC_PLUS_8 = timezone(timedelta(hours=8))
SUPPORTED_SUFFIXES = (".zip", ".dmg", ".pkg", ".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".bin", ".exe", ".sh")
MAX_RELEASE_ASSETS = 1000
MAX_ASSET_SIZE = (2 << 30) - 1


class ProgressLog:
    def __init__(self, name, persist=True):
        self.file = None
        if persist:
            self.file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=f"{name}-", suffix=".log", delete=False)
            print(f"进度日志：{self.file.name}", flush=True)
        self.log("启动")

    def log(self, message):
        line = f"[{datetime.now(UTC_PLUS_8).isoformat()}] {message}"
        if self.file is not None:
            self.file.write(line + "\n")
            self.file.flush()
        print(line, flush=True)

    def close(self):
        if self.file is not None:
            self.file.close()

    def command(self, command):
        output = bytearray()
        diagnostics = bytearray()
        environment = {name: value for name, value in os.environ.items() if name != "GH_DEBUG"}
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment) as process, DefaultSelector() as selector:
            selector.register(process.stdout, EVENT_READ, output)
            selector.register(process.stderr, EVENT_READ, diagnostics)
            try:
                while selector.get_map():
                    events = selector.select(timeout=60)
                    if not events:
                        self.log(f"{command[0]} 仍在运行")
                    for key, _ in events:
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        key.data.extend(chunk)
                        if key.data is diagnostics:
                            *lines, pending = diagnostics.split(b"\n")
                            diagnostics[:] = pending
                            for line in lines:
                                self.diagnostic(line, environment)
                if diagnostics:
                    self.diagnostic(diagnostics, environment)
                if process.wait():
                    raise ValueError(f"{command[0]} 执行失败，退出码 {process.returncode}")
            except (Exception, KeyboardInterrupt):
                process.kill()
                raise
        return bytes(output)

    def diagnostic(self, line, environment):
        message = re.sub(r"https?://\S+", "[URL]", line.decode("utf-8", errors="replace").strip())
        for name in ("GH_TOKEN", "GITHUB_TOKEN"):
            if environment.get(name):
                message = message.replace(environment[name], "[TOKEN]")
        if message:
            self.log(message)


def unique_json_object(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError(f"{MIRROR_LIST} 包含重复字段")
    return fields


def read_mirror_list(path):
    catalog = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json_object)
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError(f"{MIRROR_LIST} 必须是非空的 cask 对象")
    for token, entry in catalog.items():
        if not re.fullmatch(TOKEN_PATTERN, token) or not isinstance(entry, dict) or entry.keys() - {"version", "state"}:
            raise ValueError(f"{MIRROR_LIST} 包含无效条目：{token!r}")
        if "version" in entry:
            version = entry["version"]
            if not isinstance(version, str) or not re.fullmatch(VERSION_PATTERN, version):
                raise ValueError(f"{MIRROR_LIST} 中 {token} 的版本无效")
            release_tag(token, version)
        if "state" in entry and (
            "version" not in entry or not isinstance(entry["state"], str) or not re.fullmatch(SHA256_PATTERN, entry["state"])
        ):
            raise ValueError(f"{MIRROR_LIST} 中 {token} 的同步状态无效")
    return catalog


def update_readme(rows, progress):
    readme = ROOT / "README.md"
    try:
        current = readme.read_text(encoding="utf-8")
        before, start, rest = current.partition(CATALOG_START)
        _, end, after = rest.partition(CATALOG_END)
        if not start or not end or current.count(CATALOG_START) != 1 or current.count(CATALOG_END) != 1:
            progress.log("README.md 展示表标记缺失或重复，跳过展示更新")
            return
        updated = before + start + "\n" + "\n".join(rows) + "\n" + end + after
        if updated != current:
            readme.write_text(updated, encoding="utf-8")
            progress.log("已写入 README.md")
    except (OSError, UnicodeError) as error:
        progress.log(f"跳过 README.md 展示更新：{error}")


def proxy_prefix(value):
    if not value:
        return DEFAULT_PROXY
    if value == "direct":
        return ""
    if not re.fullmatch(r"https://[a-zA-Z0-9.-]+(?::[0-9]+)?(?:/[a-zA-Z0-9._~/-]*)?", value):
        raise ValueError("MIRROR_PROXY_PREFIX 必须为 HTTPS 前缀或 direct")
    return value.rstrip("/") + "/"


def download(progress, url, destination=None):
    command = [
        "curl", "--disable", "--fail", "--silent", "--show-error", "--location", "--globoff",
        "--proto", "=https", "--proto-redir", "=https", "--retry", "2", "--connect-timeout", "20",
    ]
    if destination is None:
        command += ["--max-time", "90", "--max-filesize", "4194304"]
    else:
        command += ["--max-time", "900", "--max-filesize", str(MAX_ASSET_SIZE), "--output", str(destination)]
    return progress.command([*command, "--", url])


def validate_upstream_metadata(token, metadata):
    commit = metadata["tap_git_head"]
    path = metadata["ruby_source_path"]
    version = metadata["version"]
    if (
        metadata["token"] != token
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or not re.fullmatch(rf"Casks/(?:[a-z0-9-]+/)*{re.escape(token)}\.rb", path)
        or not re.fullmatch(VERSION_PATTERN, version)
    ):
        raise ValueError(f"{token}：上游元数据不符合预期")
    return metadata


def upstream_metadata(progress, token):
    return validate_upstream_metadata(token, json.loads(download(progress, f"{CASK_API}/{token}.json")))


def upstream_cask(progress, token, metadata):
    commit = metadata["tap_git_head"]
    path = metadata["ruby_source_path"]
    source = download(progress, f"{UPSTREAM_RAW}/{commit}/{path}")
    if hashlib.sha256(source).hexdigest() != metadata["ruby_source_checksum"]["sha256"]:
        raise ValueError(f"{token}：上游 Ruby 源文件的 SHA-256 不匹配")
    if not source.startswith(f'cask "{token}" do\n'.encode()):
        raise ValueError(f"{token}：上游 Ruby 源文件的 cask 名称不匹配")
    return source.decode("utf-8")


def cask_versions(source):
    return {version or latest for version, latest in VERSION_STANZA.findall(source)}


def platform_metadata(metadata):
    for platform in metadata.get("supported_platforms") or ():
        yield platform, metadata | metadata["variations"].get(platform, {})


def mirror_state(repo, prefix, metadata, source):
    platforms = {
        platform: {field: target.get(field) for field in ("version", "sha256", "url", "url_specs")}
        for platform, target in platform_metadata(metadata)
    }
    state = [repo, prefix, metadata["version"], metadata["ruby_source_checksum"]["sha256"], platforms, source]
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def release_tag(token, version):
    if not re.fullmatch(TOKEN_PATTERN, token) or not re.fullmatch(VERSION_PATTERN, version) or ".." in version or version.endswith((".", ".lock")):
        raise ValueError(f"{token} {version}：无法生成安全的 Release 标签")
    return f"{MIRROR_TAG_PREFIX}{token}--{version}"


def release_links(repo, source):
    pattern = re.compile(
        rf"[\"']([^\s\"']*)https://github\.com/{re.escape(repo)}/releases/download/({MIRROR_TAG_PREFIX}[^/\s\"']+)/",
        re.IGNORECASE,
    )
    return {(prefix, unquote(tag)) for prefix, tag in pattern.findall(source)}


def platform_label(platform):
    arch = "arm64" if platform.startswith("arm64_") else "intel"
    system = "linux" if platform.endswith("_linux") else "macos"
    return f"{system}-{arch}"


def release_plan(repo, tag, prefix, metadata):
    token, version = metadata["token"], metadata["version"]
    if version == "latest":
        raise ValueError(f"{token}：无法为无固定版本的 cask 镜像安装包")
    platforms = dict(platform_metadata(metadata))
    if not platforms:
        raise ValueError(f"{token}：上游未声明支持的平台")
    files = {}
    platforms_by_checksum = {}
    for platform, target in platforms.items():
        checksum = target["sha256"]
        url = target["url"]
        if not isinstance(url, str) or not checksum or not re.fullmatch(SHA256_PATTERN, checksum):
            raise ValueError(f"{token} {platform}：安装包缺少下载地址或固定 SHA-256")
        parsed = urlsplit(url)
        name = parsed.path.rsplit("/", 1)[-1]
        if (
            parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or target.get("url_specs")
            or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?", name)
        ):
            raise ValueError(f"{token}：发现未校验的安装包或不支持的下载地址")
        if "." in name and not name.lower().endswith(SUPPORTED_SUFFIXES):
            raise ValueError(f"{token}：暂不支持镜像安装包的文件格式：{name}")
        if files.setdefault(url, (name, checksum)) != (name, checksum):
            raise ValueError(f"{token}：同一个下载地址对应不同的校验和")
        platforms_by_checksum.setdefault(checksum, set()).add(platform_label(platform))

    name_prefix = re.sub(r"[^A-Za-z0-9_-]+", "-", f"{token}-{version}")
    assets = {}
    mirror_downloads = {}
    for url, (name, checksum) in sorted(files.items()):
        if checksum in mirror_downloads:
            if mirror_downloads[checksum][1] != name:
                raise ValueError(f"{token}：相同校验和对应多个不同的附件文件名")
            continue
        labels = "-".join(sorted(platforms_by_checksum[checksum]))
        file_prefix = f"{name_prefix}-{labels}" if len(platforms_by_checksum) > 1 else name_prefix
        asset_name = f"{file_prefix}-{checksum[:16]}-{name}"
        if assets.setdefault(asset_name, (url, checksum))[1] != checksum:
            raise ValueError(f"{token}：附件文件名冲突：{asset_name}")
        mirror_url = f"{prefix}https://github.com/{repo}/releases/download/{quote(tag, safe='')}/{asset_name}"
        mirror_downloads[checksum] = mirror_url, name
    return assets, mirror_downloads


def replace_download_url(token, source, mirror_downloads):
    matches = list(URL_STANZA.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"{token}：上游需要有且仅有一个独立的顶层 URL 声明")
    match = matches[0]
    mapping = "".join(f"    {json.dumps(checksum)} => {json.dumps(download)},\n" for checksum, download in sorted(mirror_downloads.items()))
    replacement = (
        f"  mirror_download = {{\n{mapping}  }}[sha256.to_s]\n"
        f"  url(mirror_download&.first || {match[1]})\n"
        "  rename File.basename(mirror_download.first), mirror_download.last if mirror_download"
    )
    return source[:match.start()] + replacement + source[match.end():]


def gh(progress, *args):
    return progress.command(["gh", *args])


def github_api(progress, path, *args):
    return gh(progress, "api", f"https://api.github.com/{path}", "--hostname", "github.com", *args)


def github_list(progress, path):
    pages = json.loads(github_api(progress, path, "--paginate", "--slurp"))
    if not isinstance(pages, list) or not pages or not all(isinstance(page, list) for page in pages):
        raise ValueError(f"{path}：GitHub 分页结果格式不正确")
    return [item for page in pages for item in page]


def find_release(releases, tag):
    matches = [release for release in releases if release["tag_name"] == tag]
    if len(matches) > 1:
        raise ValueError(f"{tag}：发现多个同名 Release，无法确定上传目标")
    return next(iter(matches), None)


def read_release(progress, path, release_id, tag):
    release = json.loads(github_api(progress, path))
    if release["id"] != release_id or release["tag_name"] != tag:
        raise ValueError(f"{tag}：目标 Release 的标签已改变")
    if type(release["draft"]) is not bool:
        raise ValueError(f"{tag}：GitHub 返回的 Release 草稿状态无效")
    return release


def release_assets(progress, path):
    assets = github_list(progress, f"{path}/assets")
    by_name = {asset["name"]: asset for asset in assets}
    if len(by_name) != len(assets):
        raise ValueError(f"{path}：GitHub 返回了重名附件")
    return by_name


def asset_matches(asset, checksum):
    return asset is not None and asset["state"] == "uploaded" and asset.get("digest") == f"sha256:{checksum}"


def publish_release(repo, tag, title, assets, release, progress):
    endpoint = f"repos/{repo}/releases"
    if len(assets) > MAX_RELEASE_ASSETS:
        raise ValueError(f"{tag}：附件数量超过 {MAX_RELEASE_ASSETS} 个的上限")

    existing_assets = {}
    if release is not None:
        release_id = release["id"]
        if type(release_id) is not int or release_id <= 0 or release["tag_name"] != tag:
            raise ValueError(f"{tag}：GitHub 返回的 Release 不匹配")
        release_path = f"{endpoint}/{release_id}"
        existing_assets = release_assets(progress, release_path)
        release = read_release(progress, release_path, release_id, tag)
    was_draft = release is None or release["draft"]
    missing = {name: package for name, package in assets.items() if not asset_matches(existing_assets.get(name), package[1])}
    if not was_draft:
        if conflicts := missing.keys() & existing_assets.keys():
            raise ValueError(f"{tag}：已发布附件不匹配，停止自动替换：{', '.join(sorted(conflicts))}")
        if not missing:
            progress.log(f"{tag}：附件已完整，复用已有 Release")
            return
    if release and release.get("immutable"):
        raise ValueError(f"{tag}：Release 已设为不可变，无法上传附件")
    stale_ids = [asset["id"] for name, asset in existing_assets.items() if was_draft and (name in missing or name not in assets)]
    if not all(type(asset_id) is int and asset_id > 0 for asset_id in stale_ids):
        raise ValueError(f"{tag}：GitHub 返回了无效的附件 ID")
    if len(existing_assets) - len(stale_ids) + len(missing) > MAX_RELEASE_ASSETS:
        raise ValueError(f"{tag}：附件数量超过 {MAX_RELEASE_ASSETS} 个的上限")

    with tempfile.TemporaryDirectory(prefix="brew-mirror-") as directory:
        paths = []
        for index, (name, (url, checksum)) in enumerate(missing.items(), 1):
            progress.log(f"{tag}：开始下载附件 {name}（{index}/{len(missing)}）")
            path = Path(directory) / name
            download(progress, url, path)
            with path.open("rb") as package:
                actual = hashlib.file_digest(package, "sha256").hexdigest()
            if path.stat().st_size > MAX_ASSET_SIZE or actual != checksum:
                raise ValueError(f"{tag}/{name}：上游安装包超过大小限制或 SHA-256 不匹配")
            paths.append(path)
            progress.log(f"{tag}：附件校验通过 {name}（{index}/{len(missing)}）")

        if release is None:
            progress.log(f"{tag}：创建 Release")
            release = json.loads(github_api(
                progress, endpoint, "--method", "POST", "--raw-field", f"tag_name={tag}", "--field", "draft=true",
                "--raw-field", "make_latest=false", "--raw-field", f"name={title}",
            ))

        release_id = release["id"]
        if type(release_id) is not int or release_id <= 0 or release["tag_name"] != tag:
            raise ValueError(f"{tag}：GitHub 返回的 Release 不匹配")
        release_path = f"{endpoint}/{release_id}"
        release = read_release(progress, release_path, release_id, tag)
        if release["draft"] != was_draft or release.get("immutable"):
            raise ValueError(f"{tag}：Release 状态已改变，停止修改附件")
        upload_url = release["upload_url"].removesuffix("{?name,label}")
        if upload_url.lower() != f"https://uploads.github.com/{release_path}/assets".lower():
            raise ValueError(f"{tag}：GitHub 返回的上传地址不匹配")
        if stale_ids:
            progress.log(f"{tag}：清理草稿中的无效附件 {len(stale_ids)} 个")
        for asset_id in stale_ids:
            github_api(progress, f"{endpoint}/assets/{asset_id}", "--method", "DELETE")
        for index, path in enumerate(paths, 1):
            progress.log(f"{tag}：开始上传附件 {path.name}（{index}/{len(paths)}）")
            gh(progress, "api", f"{upload_url}?name={quote(path.name)}", "--hostname", "github.com", "--method", "POST",
               "--header", "Content-Type: application/octet-stream", "--input", str(path))
            progress.log(f"{tag}：附件上传完成 {path.name}（{index}/{len(paths)}）")

    uploaded = release_assets(progress, release_path)
    if (was_draft and uploaded.keys() != assets.keys()) or not all(
        asset_matches(uploaded.get(name), checksum) for name, (_, checksum) in assets.items()
    ):
        raise ValueError(f"{tag}：GitHub 附件不完整或 SHA-256 不匹配")
    release = read_release(progress, release_path, release_id, tag)
    if release["draft"] != was_draft:
        raise ValueError(f"{tag}：Release 状态已改变，停止发布")
    if was_draft:
        release = json.loads(github_api(
            progress, release_path, "--method", "PATCH", "--field", "draft=false", "--raw-field", "make_latest=false", "--raw-field", f"name={title}",
        ))
    if release["draft"] is not False or release["id"] != release_id or release["tag_name"] != tag or (was_draft and release["name"] != title):
        raise ValueError(f"{tag}：未找到已发布的目标 Release")
    progress.log(f"{tag}：Release 发布完成")


def sync(repo, prefix, check, progress):
    catalog_path = ROOT / MIRROR_LIST
    catalog = read_mirror_list(catalog_path)

    rows = [TABLE_HEADER]
    updated_catalog = {}
    definitions = {}
    release_plans = []
    progress.log(f"共 {len(catalog)} 个 cask")
    for index, (token, entry) in enumerate(catalog.items(), 1):
        progress.log(f"开始处理 cask {token}（{index}/{len(catalog)}）")
        metadata = upstream_metadata(progress, token)
        version = metadata["version"]
        tag = release_tag(token, version)
        path = ROOT / "Casks" / f"{token}.rb"
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        state = mirror_state(repo, prefix, metadata, current)
        if not check and current and state == entry.get("state"):
            progress.log(f"{token} {version}：上游定义、安装包和镜像地址未变化，跳过（{index}/{len(catalog)}）")
        else:
            source = upstream_cask(progress, token, metadata)
            assets, mirror_downloads = release_plan(repo, tag, prefix, metadata)
            source = replace_download_url(token, source, mirror_downloads)
            if source != current:
                definitions[path] = source
                state = mirror_state(repo, prefix, metadata, source)
                release_plans.append((tag, f"Homebrew 镜像 {token} {version}", assets))
            progress.log(f"{token} {version}：已检查 {tag}，{len(assets)} 个附件（{index}/{len(catalog)}）")
        updated_catalog[token] = {"version": version, "state": state}
        source_path = quote(metadata["ruby_source_path"])
        rows.append(f"| [`{token}`]({CASK_SOURCE_PAGE}/{source_path}) | `{version}` | GitHub Releases |")

    if check:
        progress.log("检查完成，不下载安装包、不操作 Release、不写入文件。")
        return

    releases = github_list(progress, f"repos/{repo}/releases") if release_plans else []
    for index, (tag, title, assets) in enumerate(release_plans, 1):
        progress.log(f"{tag}：开始同步 Release（{index}/{len(release_plans)}）")
        release = find_release(releases, tag)
        publish_release(repo, tag, title, assets, release, progress)
        progress.log(f"{tag}：Release 同步完成（{index}/{len(release_plans)}）")

    if updated_catalog != catalog:
        definitions[catalog_path] = json.dumps(updated_catalog, indent=2) + "\n"
    for path, contents in definitions.items():
        path.write_text(contents, encoding="utf-8")
        progress.log(f"已写入 {path.relative_to(ROOT)}")
    update_readme(rows, progress)


def main():
    parser = argparse.ArgumentParser(description="同步 Homebrew 官方 cask")
    parser.add_argument("--check", action="store_true", help="仅检查，不下载附件、发布或写入文件")
    args = parser.parse_args()
    progress = ProgressLog("homebrew-mirror-sync", persist=not args.check)
    try:
        repo = os.environ.get("GITHUB_REPOSITORY", "akiakise/homebrew-mirror")
        if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repo):
            raise ValueError("GITHUB_REPOSITORY 必须为 owner/repo")
        prefix = proxy_prefix(os.environ.get("MIRROR_PROXY_PREFIX", "").strip())
        progress.log(f"开始同步：仓库 {repo}，检查模式 {args.check}")
        sync(repo, prefix, args.check, progress)
        progress.log("同步成功")
    except KeyboardInterrupt:
        progress.log("同步取消")
        sys.exit(130)
    except (ValueError, KeyError, OSError, TypeError) as error:
        progress.log(f"同步失败：{error}")
        raise
    finally:
        progress.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError) as error:
        sys.exit(f"同步失败：{error}")
