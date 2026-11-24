import argparse
from datetime import datetime, timedelta
import os
import re
import sys

from sync_casks import MIRROR_TAG_PREFIX, ROOT, UTC_PLUS_8, github_api, github_list, read_release


RETENTION_DAYS = 7


def referenced_tags(repo):
    pattern = re.compile(rf"https://github\.com/{re.escape(repo)}/releases/download/({MIRROR_TAG_PREFIX}[^/\s\"']+)/", re.IGNORECASE)
    casks = sorted((ROOT / "Casks").rglob("*.rb"))
    if not casks:
        raise ValueError("未找到 cask 定义，停止清理")
    return {tag for cask in casks for tag in pattern.findall(cask.read_text(encoding="utf-8"))}


def is_expired(release, cutoff, references):
    tag = release["tag_name"]
    if not tag.startswith(MIRROR_TAG_PREFIX) or tag in references or release["draft"]:
        return False
    published_at = release["published_at"]
    if not isinstance(published_at, str) or (published := datetime.fromisoformat(published_at)).tzinfo is None:
        raise ValueError(f"{tag}：GitHub 返回的发布时间无效")
    return published <= cutoff


def cleanup(repo, cutoff, delete):
    references = referenced_tags(repo)
    endpoint = f"repos/{repo}/releases"
    candidates = []
    for release in github_list(endpoint):
        if not is_expired(release, cutoff, references):
            continue
        tag = release["tag_name"]
        release_id = release["id"]
        if type(release_id) is not int or release_id <= 0:
            raise ValueError(f"{tag}：GitHub 返回了无效的 Release ID")
        candidates.append((tag, release_id))

    if not candidates:
        print("没有可清理的历史镜像 Release。")

    for tag, release_id in candidates:
        if not delete:
            print(f"预览：将清理 {tag}")
            continue
        path = f"{endpoint}/{release_id}"
        if not is_expired(read_release(path, release_id, tag), cutoff, references):
            print(f"{tag}：不再满足清理条件，跳过")
            continue
        github_api(path, "--method", "DELETE")
        print(f"已清理：{tag}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="清理已满 7 天且未被引用的镜像 Release")
    parser.add_argument("--delete", action="store_true", help="执行删除；不传此参数时仅预览")
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repo):
        raise ValueError("GITHUB_REPOSITORY 必须为 owner/repo")
    cleanup(repo, datetime.now(UTC_PLUS_8) - timedelta(days=RETENTION_DAYS), args.delete)


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError) as error:
        sys.exit(f"清理失败：{error}")
