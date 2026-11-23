import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import quote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
CATALOG_START = "<!-- mirror-catalog:start -->"
CATALOG_END = "<!-- mirror-catalog:end -->"
TABLE_HEADER = "| Cask | Homebrew 上游版本 | 下载来源 |\n| --- | --- | --- |"
TOKEN_PATTERN = r"[a-z0-9]+(?:[-@+.][a-z0-9]+)*"
ROW_PATTERN = re.compile(rf"\| `({TOKEN_PATTERN})` \| [^|]+ \| [^|]+ \|")
URL_STANZA = re.compile(r'^  url ("(?:[^"\\#\n]|\\[^\n]|#\{[^{}\n]+\})+")$', re.MULTILINE)
VERSION_STANZA = re.compile(r'^  version "([^"]+)"$', re.MULTILINE)
SHA256_PATTERN = r"[0-9a-f]{64}"
CASK_API = "https://formulae.brew.sh/api/cask"
UPSTREAM_RAW = "https://raw.githubusercontent.com/Homebrew/homebrew-cask"
DEFAULT_PROXY = "https://gh-proxy.com/"
MIRROR_TAG_PREFIX = "mirror-"
RELEASE_DATE_PATTERN = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
UTC_PLUS_8 = timezone(timedelta(hours=8))
SUPPORTED_SUFFIXES = (".zip", ".dmg", ".pkg", ".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".bin", ".exe", ".sh")
MAX_RELEASE_ASSETS = 1000
MAX_ASSET_SIZE = (2 << 30) - 1


def parse_catalog(readme):
    before, start, rest = readme.partition(CATALOG_START)
    table, end, after = rest.partition(CATALOG_END)
    if not start or not end or readme.count(CATALOG_START) != 1 or readme.count(CATALOG_END) != 1:
        raise ValueError("README.md 必须包含唯一一对镜像清单标记")

    rows = table.strip().splitlines()
    if rows[:2] != TABLE_HEADER.splitlines() or len(rows) < 3:
        raise ValueError("README.md 的镜像清单表头不正确或清单为空")
    tokens = []
    for row in rows[2:]:
        match = ROW_PATTERN.fullmatch(row)
        if not match or match[1] in tokens:
            raise ValueError(f"README.md 中的镜像清单行格式不正确或重复：{row}")
        tokens.append(match[1])
    return before + start, tokens, end + after


def proxy_prefix(value):
    if not value:
        return DEFAULT_PROXY
    if value == "direct":
        return ""
    if not re.fullmatch(r"https://[a-zA-Z0-9.-]+(?::[0-9]+)?(?:/[a-zA-Z0-9._~/-]*)?", value):
        raise ValueError("MIRROR_PROXY_PREFIX 必须为 HTTPS 前缀或 direct")
    return value.rstrip("/") + "/"


def download(url, destination=None):
    command = [
        "curl", "--disable", "--fail", "--silent", "--show-error", "--location", "--globoff",
        "--proto", "=https", "--proto-redir", "=https", "--retry", "2", "--connect-timeout", "20",
    ]
    if destination is None:
        command += ["--max-time", "90", "--max-filesize", "4194304"]
    else:
        command += ["--max-time", "900", "--max-filesize", str(MAX_ASSET_SIZE), "--output", str(destination)]
    return subprocess.run([*command, "--", url], check=True, stdout=subprocess.PIPE).stdout


def validate_upstream_metadata(token, metadata):
    commit = metadata["tap_git_head"]
    path = metadata["ruby_source_path"]
    version = metadata["version"]
    if (
        metadata["token"] != token
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or not re.fullmatch(rf"Casks/(?:[a-z0-9-]+/)*{re.escape(token)}\.rb", path)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._,+-]*", version)
    ):
        raise ValueError(f"{token}：上游元数据不符合预期")
    return metadata


def upstream_metadata(token):
    return validate_upstream_metadata(token, json.loads(download(f"{CASK_API}/{token}.json")))


def upstream_cask(token, metadata=None):
    metadata = metadata or upstream_metadata(token)
    commit = metadata["tap_git_head"]
    path = metadata["ruby_source_path"]
    source = download(f"{UPSTREAM_RAW}/{commit}/{path}")
    if hashlib.sha256(source).hexdigest() != metadata["ruby_source_checksum"]["sha256"]:
        raise ValueError(f"{token}：上游 Ruby 源文件的 SHA-256 不匹配")
    if not source.startswith(f'cask "{token}" do\n'.encode()):
        raise ValueError(f"{token}：上游 Ruby 源文件的 cask 名称不匹配")
    return metadata, source.decode("utf-8")


def local_cask_version(token):
    path = ROOT / "Casks" / f"{token}.rb"
    if not path.is_file():
        return None
    match = VERSION_STANZA.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def platform_label(platform):
    arch = "arm64" if platform.startswith("arm64_") else "intel"
    system = "linux" if platform.endswith("_linux") else "macos"
    return f"{system}-{arch}"


def release_plan(repo, tag, prefix, metadata):
    token, version = metadata["token"], metadata["version"]
    if version == "latest":
        raise ValueError(f"{token}：无法为无固定版本的 cask 镜像安装包")
    platforms = metadata.get("supported_platforms")
    if not platforms:
        raise ValueError(f"{token}：上游未声明支持的平台")
    files = {}
    platforms_by_checksum = {}
    for platform in platforms:
        target = metadata | metadata["variations"].get(platform, {})
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
        mirror_url = f"{prefix}https://github.com/{repo}/releases/download/{tag}/{asset_name}"
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


def gh(*args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"gh {' '.join(args[:2])} 失败：{result.stderr.strip()}")
    return result.stdout


def github_api(path, *args):
    return gh("api", f"https://api.github.com/{path}", "--hostname", "github.com", *args)


def github_list(path):
    pages = json.loads(github_api(path, "--paginate", "--slurp"))
    if not isinstance(pages, list) or not pages or not all(isinstance(page, list) for page in pages):
        raise ValueError(f"{path}：GitHub 分页结果格式不正确")
    return [item for page in pages for item in page]


def find_release(repo, tag):
    releases = github_list(f"repos/{repo}/releases")
    matches = [release for release in releases if release["tag_name"] == tag]
    if len(matches) > 1:
        raise ValueError(f"{tag}：发现多个同名 Release，无法确定上传目标")
    return next(iter(matches), None)


def read_release(path, release_id, tag):
    release = json.loads(github_api(path))
    if release["id"] != release_id or release["tag_name"] != tag:
        raise ValueError(f"{tag}：目标 Release 的标签已改变")
    return release


def release_has_assets(path, assets):
    uploaded = github_list(f"{path}/assets")
    expected = {name: f"sha256:{checksum}" for name, (_, checksum) in assets.items()}
    actual = {asset["name"]: asset.get("digest") for asset in uploaded if asset["state"] == "uploaded"}
    return len(uploaded) == len(expected) and actual == expected


def publish_release(repo, tag, title, assets, release):
    endpoint = f"repos/{repo}/releases"
    if release and release.get("immutable"):
        raise ValueError(f"{tag}：Release 已设为不可变，无法清理并重新上传附件")
    if len(assets) > MAX_RELEASE_ASSETS:
        raise ValueError(f"{tag}：附件数量超过 {MAX_RELEASE_ASSETS} 个的上限")

    with tempfile.TemporaryDirectory(prefix="brew-mirror-") as directory:
        paths = []
        for name, (url, checksum) in assets.items():
            path = Path(directory) / name
            download(url, path)
            with path.open("rb") as package:
                actual = hashlib.file_digest(package, "sha256").hexdigest()
            if path.stat().st_size > MAX_ASSET_SIZE or actual != checksum:
                raise ValueError(f"{tag}/{name}：上游安装包超过大小限制或 SHA-256 不匹配")
            paths.append(path)

        if release is None:
            release = json.loads(github_api(
                endpoint, "--method", "POST", "--raw-field", f"tag_name={tag}", "--field", "draft=true",
                "--raw-field", "make_latest=false", "--raw-field", f"name={title}",
            ))

        release_id = release["id"]
        if type(release_id) is not int or release_id <= 0 or release["tag_name"] != tag:
            raise ValueError(f"{tag}：GitHub 返回的 Release 不匹配")
        release_path = f"{endpoint}/{release_id}"
        old_assets = github_list(f"{release_path}/assets")
        release = read_release(release_path, release_id, tag)
        if release.get("immutable"):
            raise ValueError(f"{tag}：Release 已设为不可变，无法清理并重新上传附件")
        upload_url = release["upload_url"].removesuffix("{?name,label}")
        if upload_url.lower() != f"https://uploads.github.com/{release_path}/assets".lower():
            raise ValueError(f"{tag}：GitHub 返回的上传地址不匹配")
        asset_ids = [asset["id"] for asset in old_assets]
        if not all(type(asset_id) is int and asset_id > 0 for asset_id in asset_ids):
            raise ValueError(f"{tag}：GitHub 返回了无效的附件 ID")
        for asset_id in asset_ids:
            github_api(f"{endpoint}/assets/{asset_id}", "--method", "DELETE")
        for path in paths:
            gh("api", f"{upload_url}?name={quote(path.name)}", "--hostname", "github.com", "--method", "POST",
               "--header", "Content-Type: application/octet-stream", "--input", str(path))

    if not release_has_assets(release_path, assets):
        raise ValueError(f"{tag}：GitHub 附件不完整或 SHA-256 不匹配")
    release = read_release(release_path, release_id, tag)
    if release["draft"] or release["name"] != title:
        release = json.loads(github_api(
            release_path, "--method", "PATCH", "--field", "draft=false", "--raw-field", "make_latest=false", "--raw-field", f"name={title}",
        ))
    if release["draft"] or release["id"] != release_id or release["tag_name"] != tag or release["name"] != title:
        raise ValueError(f"{tag}：未找到已发布的目标 Release")


def sync(repo, run_date, allowed, prefix, check):
    tag = f"{MIRROR_TAG_PREFIX}{run_date}"
    title = f"Homebrew 镜像 {run_date}"
    readme = ROOT / "README.md"
    before, tokens, after = parse_catalog(readme.read_text(encoding="utf-8"))
    if allowed - set(tokens):
        raise ValueError(f"MIRROR_ALLOWED_CASKS 包含不在 README.md 清单中的名称：{', '.join(sorted(allowed - set(tokens)))}")

    metadata_by_token = {token: upstream_metadata(token) for token in tokens}

    version_tokens = allowed or set(tokens)
    if not check and all(local_cask_version(token) == metadata_by_token[token]["version"] for token in version_tokens):
        print("所有已启用镜像 cask 版本均未更新，跳过下载、Release 覆盖和文件写入。")
        return

    upstream = {token: upstream_cask(token, metadata_by_token[token]) for token in tokens}
    rows = [TABLE_HEADER]
    definitions = {}
    pending = {}
    for token in tokens:
        metadata, source = upstream[token]
        version = metadata["version"]
        status = "上游直连"
        if token in allowed:
            assets, mirror_downloads = release_plan(repo, tag, prefix, metadata)
            source = replace_download_url(token, source, mirror_downloads)
            if pending.keys() & assets.keys():
                raise ValueError(f"{token}：附件文件名与其他 cask 冲突")
            pending.update(assets)
            status = "GitHub Releases"
        print(f"{token} {version}：{status}", flush=True)
        rows.append(f"| `{token}` | `{version}` | {status} |")
        definitions[ROOT / "Casks" / f"{token}.rb"] = source

    if check:
        target = f"{len(pending)} 个附件统一存入 {tag}" if pending else "无需发布附件"
        print(f"检查完成：{target}，不执行发布。")
        return

    definitions[readme] = before + "\n" + "\n".join(rows) + "\n" + after
    link_pattern = re.compile(rf"(https://github\.com/{re.escape(repo)}/releases/download/)({MIRROR_TAG_PREFIX}{RELEASE_DATE_PATTERN})/")
    current = {path: path.read_text(encoding="utf-8") for path in definitions if path.is_file()}
    unchanged = all(
        path in current and link_pattern.sub(r"\1", current[path]) == link_pattern.sub(r"\1", contents)
        for path, contents in definitions.items()
    )
    release = find_release(repo, tag) if pending else None
    if unchanged and release is None:
        previous_tags = {match[2] for path, contents in current.items() if path != readme for match in link_pattern.finditer(contents)}
        previous = find_release(repo, next(iter(previous_tags))) if len(previous_tags) == 1 else None
        if not pending or (
            previous and not previous["draft"] and release_has_assets(f"repos/{repo}/releases/{previous['id']}", pending)
        ):
            print("上游定义与镜像配置没有变化，跳过发布。")
            return
    if pending:
        publish_release(repo, tag, title, pending, release)
    for path, contents in definitions.items():
        path.write_text(contents, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="同步 Homebrew 官方 cask")
    parser.add_argument("--check", action="store_true", help="仅检查，不下载附件、发布或写入文件")
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "akiakise/homebrew-mirror")
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repo):
        raise ValueError("GITHUB_REPOSITORY 必须为 owner/repo")
    allowed = set(filter(None, re.split(r"[\s,]+", os.environ.get("MIRROR_ALLOWED_CASKS", ""))))
    prefix = proxy_prefix(os.environ.get("MIRROR_PROXY_PREFIX", "").strip())
    run_date = datetime.now(UTC_PLUS_8).date().isoformat()
    sync(repo, run_date, allowed, prefix, args.check)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"同步失败：{error}")
