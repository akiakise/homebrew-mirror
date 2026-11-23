import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CATALOG_START = "<!-- mirror-catalog:start -->"
CATALOG_END = "<!-- mirror-catalog:end -->"
TABLE_HEADER = "| Cask | Homebrew 上游版本 | 下载来源 |\n| --- | --- | --- |"
TOKEN_PATTERN = r"[a-z0-9]+(?:[-@+.][a-z0-9]+)*"
ROW_PATTERN = re.compile(rf"\| `({TOKEN_PATTERN})` \| [^|]+ \| [^|]+ \|")
URL_STANZA = re.compile(r'^  url ("(?:[^"\\#\n]|\\[^\n]|#\{[^{}\n]+\})+")$', re.MULTILINE)
SHA256_PATTERN = r"[0-9a-f]{64}"
CASK_API = "https://formulae.brew.sh/api/cask"
UPSTREAM_RAW = "https://raw.githubusercontent.com/Homebrew/homebrew-cask"
DEFAULT_PROXY = "https://gh-proxy.com/"
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


def upstream_cask(token):
    metadata = json.loads(download(f"{CASK_API}/{token}.json"))
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
    source = download(f"{UPSTREAM_RAW}/{commit}/{path}")
    if hashlib.sha256(source).hexdigest() != metadata["ruby_source_checksum"]["sha256"]:
        raise ValueError(f"{token}：上游 Ruby 源文件的 SHA-256 不匹配")
    if not source.startswith(f'cask "{token}" do\n'.encode()):
        raise ValueError(f"{token}：上游 Ruby 源文件的 cask 名称不匹配")
    return metadata, source.decode("utf-8")


def release_plan(repo, prefix, metadata):
    token, version = metadata["token"], metadata["version"]
    if version == "latest":
        raise ValueError(f"{token}：无法为无固定版本的 cask 镜像安装包")
    targets = [metadata, *(metadata | delta for delta in metadata["variations"].values())]
    files = {}
    hashes_by_name = {}
    for target in targets:
        checksum = target["sha256"]
        if target is not metadata and checksum is None:
            continue
        url = target["url"]
        parsed = urlsplit(url)
        name = parsed.path.rsplit("/", 1)[-1]
        if (
            not checksum or not re.fullmatch(SHA256_PATTERN, checksum)
            or parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or target.get("url_specs")
            or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?", name)
        ):
            raise ValueError(f"{token}：发现未校验的安装包或不支持的下载地址")
        if files.setdefault(url, (name, checksum)) != (name, checksum):
            raise ValueError(f"{token}：同一个下载地址对应不同的校验和")
        hashes_by_name.setdefault(name, set()).add(checksum)

    fingerprint = hashlib.sha256(json.dumps(sorted(set(files.values()))).encode()).hexdigest()[:16]
    tag_version = re.sub(r"[^A-Za-z0-9.-]+|\.{2,}", "-", version)
    base_tag = f"mirror-{token}-{tag_version}-{fingerprint}"
    releases = {}
    mirror_urls = {}
    for url, (name, checksum) in sorted(files.items()):
        tag = base_tag if len(hashes_by_name[name]) == 1 else f"{base_tag}-{checksum[:16]}"
        releases.setdefault(tag, {}).setdefault(name, (url, checksum))
        mirror_url = f"{prefix}https://github.com/{repo}/releases/download/{tag}/{name}"
        if mirror_urls.setdefault(checksum, mirror_url) != mirror_url:
            raise ValueError(f"{token}：相同校验和对应多个不同的附件文件名")
    return releases, mirror_urls


def replace_download_url(token, source, mirror_urls):
    matches = list(URL_STANZA.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"{token}：上游需要有且仅有一个独立的顶层 URL 声明")
    match = matches[0]
    mapping = "".join(f"    {json.dumps(checksum)} => {json.dumps(url)},\n" for checksum, url in sorted(mirror_urls.items()))
    replacement = f"  url({{\n{mapping}  }}.fetch(sha256.to_s) {{ {match[1]} }})"
    return source[:match.start()] + replacement + source[match.end():]


def gh(repo, *args, allow_not_found=False):
    result = subprocess.run(["gh", *args, "--repo", repo], capture_output=True, text=True)
    if allow_not_found and result.returncode == 1 and result.stderr.strip() == "release not found":
        return None
    if result.returncode:
        raise ValueError(f"gh {' '.join(args[:2])} 失败：{result.stderr.strip()}")
    return result.stdout


def view_release(repo, tag):
    output = gh(repo, "release", "view", tag, "--json", "assets,isDraft", allow_not_found=True)
    return None if output is None else json.loads(output)


def missing_assets(tag, expected, release):
    existing = {asset["name"]: asset for asset in release["assets"]} if release else {}
    missing = []
    placeholders = []
    for name, (_, checksum) in expected.items():
        asset = existing.get(name)
        if asset is None:
            missing.append(name)
        elif release["isDraft"] and asset["state"] == "starter" and asset["size"] == 0:
            missing.append(name)
            placeholders.append(name)
        elif asset["state"] != "uploaded" or asset.get("digest") != f"sha256:{checksum}":
            raise ValueError(f"{tag}/{name}：GitHub 上的附件摘要或状态不匹配")
    return missing, placeholders


def publish_release(repo, tag, assets):
    release = view_release(repo, tag)
    missing, placeholders = missing_assets(tag, assets, release)
    if release and not release["isDraft"]:
        if missing:
            raise ValueError(f"{tag}：已发布的 Release 缺少附件：{', '.join(missing)}")
        return

    if missing:
        with tempfile.TemporaryDirectory(prefix="brew-mirror-") as directory:
            paths = []
            for name in missing:
                url, checksum = assets[name]
                path = Path(directory) / name
                download(url, path)
                with path.open("rb") as package:
                    actual = hashlib.file_digest(package, "sha256").hexdigest()
                if path.stat().st_size > MAX_ASSET_SIZE or actual != checksum:
                    raise ValueError(f"{tag}/{name}：上游安装包超过大小限制或 SHA-256 不匹配")
                paths.append(str(path))
            if release is None:
                gh(repo, "release", "create", tag, *paths, "--draft", "--latest=false",
                   "--title", tag, "--notes", "原样同步自 Homebrew cask 指定的上游下载地址。")
            else:
                for name in placeholders:
                    gh(repo, "release", "delete-asset", tag, name, "--yes")
                gh(repo, "release", "upload", tag, *paths)

    release = view_release(repo, tag)
    if release is None or missing_assets(tag, assets, release)[0]:
        raise ValueError(f"{tag}：未找到完整的已校验附件")
    gh(repo, "release", "edit", tag, "--draft=false", "--latest=false")


def sync(repo, allowed, prefix, check):
    readme = ROOT / "README.md"
    before, tokens, after = parse_catalog(readme.read_text(encoding="utf-8"))
    if allowed - set(tokens):
        raise ValueError(f"MIRROR_ALLOWED_CASKS 包含不在 README.md 清单中的名称：{', '.join(sorted(allowed - set(tokens)))}")

    rows = [TABLE_HEADER]
    definitions = {}
    pending = {}
    for token in tokens:
        metadata, source = upstream_cask(token)
        version = metadata["version"]
        status = "上游直连"
        if token in allowed:
            releases, mirror_urls = release_plan(repo, prefix, metadata)
            source = replace_download_url(token, source, mirror_urls)
            pending.update(releases)
            status = "GitHub Releases"
        print(f"{token} {version}：{status}", flush=True)
        rows.append(f"| `{token}` | `{version}` | {status} |")
        definitions[ROOT / "Casks" / f"{token}.rb"] = source

    if check:
        print(f"检查完成：计划使用 {len(pending)} 个 Release、{sum(map(len, pending.values()))} 个附件，不执行发布。")
        return

    for tag, assets in pending.items():
        publish_release(repo, tag, assets)
    definitions[readme] = before + "\n" + "\n".join(rows) + "\n" + after
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
    sync(repo, allowed, prefix, args.check)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"同步失败：{error}")
