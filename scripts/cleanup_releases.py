import argparse
from datetime import datetime, timedelta
import json
import os
import re
import sys

from sync_casks import (
    MIRROR_LIST,
    MIRROR_TAG_PREFIX,
    ROOT,
    VERSIONED_TAG,
    ProgressLog,
    UTC_PLUS_8,
    cask_versions,
    gh,
    github_api,
    read_mirror_list,
    read_release,
    release_links,
    release_tag,
)


RETENTION_DAYS = 7
LEGACY_TAG = re.compile(rf"{MIRROR_TAG_PREFIX}[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}")
RELEASES_QUERY = """
query($owner: String!, $name: String!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    releases(first: 100, after: $endCursor) {
      nodes { databaseId tagName createdAt isDraft }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def protected_tags(repo):
    catalog = read_mirror_list(ROOT / MIRROR_LIST)
    sources = {path: path.read_text(encoding="utf-8") for path in (ROOT / "Casks").rglob("*.rb")}
    protected = {tag for source in sources.values() for _, tag in release_links(repo, source)}
    for token, entry in catalog.items():
        version = entry.get("version")
        source = sources.get(ROOT / "Casks" / f"{token}.rb", "")
        if version not in cask_versions(source):
            raise ValueError(f"{token}：清单主版本与默认分支 cask 定义不一致，停止清理")
        if version != "latest":
            protected.add(release_tag(token, version))
    return protected


def listed_releases(progress, repo):
    owner, name = repo.split("/")
    pages = json.loads(gh(
        progress, "api", "graphql", "--hostname", "github.com", "--paginate", "--slurp",
        "--raw-field", f"query={RELEASES_QUERY}", "--raw-field", f"owner={owner}", "--raw-field", f"name={name}",
    ))
    if not isinstance(pages, list) or not pages:
        raise ValueError("GitHub Release 分页结果无效")
    releases = []
    for page in pages:
        if "errors" in page or not page["data"]["repository"]:
            raise ValueError("无法读取 GitHub Release 创建时间，停止清理")
        releases.extend(page["data"]["repository"]["releases"]["nodes"])
    return releases


def is_expired(release, cutoff, protected):
    tag = release["tagName"]
    if tag in protected or release["isDraft"] is not False or not (LEGACY_TAG.fullmatch(tag) or VERSIONED_TAG.fullmatch(tag)):
        return False
    created_at = release["createdAt"]
    if not isinstance(created_at, str) or (created := datetime.fromisoformat(created_at)).tzinfo is None:
        raise ValueError(f"{tag}：GitHub 返回的创建时间无效")
    return created <= cutoff


def cleanup(repo, cutoff, delete, progress):
    if delete:
        git = ["git", "-C", str(ROOT)]
        checkout = progress.command([*git, "rev-parse", "--verify", "HEAD"]).strip()
        if progress.command([*git, "status", "--porcelain", "--", MIRROR_LIST, "Casks/"]).strip():
            raise ValueError("当前工作树的镜像清单或 cask 有未提交改动，停止清理")
    protected = protected_tags(repo)
    progress.log(f"开始扫描 Release：保护 {len(protected)} 个当前版本或引用标签")
    endpoint = f"repos/{repo}/releases"
    candidates = []
    for release in listed_releases(progress, repo):
        if not is_expired(release, cutoff, protected):
            continue
        tag = release["tagName"]
        release_id = release["databaseId"]
        if type(release_id) is not int or release_id <= 0:
            raise ValueError(f"{tag}：GitHub 返回了无效的 Release ID")
        candidates.append((tag, release_id))

    if not candidates:
        progress.log("没有可清理的历史镜像 Release。")

    for index, (tag, release_id) in enumerate(candidates, 1):
        progress.log(f"检查清理目标 {tag}（{index}/{len(candidates)}）")
        if not delete:
            progress.log(f"预览：将清理 {tag}（{index}/{len(candidates)}）")
            continue
        path = f"{endpoint}/{release_id}"
        if read_release(progress, path, release_id, tag)["draft"]:
            progress.log(f"{tag}：不再满足清理条件，跳过（{index}/{len(candidates)}）")
            continue
        remote = progress.command([*git, "ls-remote", "--exit-code", f"https://github.com/{repo}.git", "HEAD"])
        if checkout + b"\tHEAD" not in remote.splitlines():
            raise ValueError("默认分支已变化或当前检出不是默认分支最新提交，停止清理")
        github_api(progress, path, "--method", "DELETE")
        progress.log(f"已清理：{tag}（{index}/{len(candidates)}）")


def main():
    parser = argparse.ArgumentParser(description="清理创建已满 7 天的历史镜像 Release，保留当前版本和引用")
    parser.add_argument("--delete", action="store_true", help="执行删除；不传此参数时仅预览")
    args = parser.parse_args()
    progress = ProgressLog("homebrew-mirror-cleanup")
    try:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repo):
            raise ValueError("GITHUB_REPOSITORY 必须为 owner/repo")
        cutoff = datetime.now(UTC_PLUS_8) - timedelta(days=RETENTION_DAYS)
        progress.log(f"开始清理：仓库 {repo}，创建时间截止 {cutoff.isoformat()}，删除模式 {args.delete}")
        cleanup(repo, cutoff, args.delete, progress)
        progress.log("清理成功")
    except KeyboardInterrupt:
        progress.log("清理取消")
        sys.exit(130)
    except (KeyError, OSError, TypeError, ValueError) as error:
        progress.log(f"清理失败：{error}")
        raise
    finally:
        progress.close()


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError) as error:
        sys.exit(f"清理失败：{error}")
