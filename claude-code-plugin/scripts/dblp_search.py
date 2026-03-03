#!/usr/bin/env python3
"""
DBLP API 封装
用于按标题查找 DBLP key 并获取权威 BibTeX。
DBLP 的 BibTeX 经人工审核，是 CS/AI 领域最权威的 BibTeX 来源。

API 文档: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
"""

import json
import sys
import time
from typing import Optional, List, Dict, Any
from urllib.parse import quote_plus
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# DBLP 主站 + 镜像，主站 500 时自动 fallback
DBLP_HOSTS = ["https://dblp.org", "https://dblp.uni-trier.de"]

# 请求间隔（秒），DBLP 无严格速率限制但需礼貌访问
REQUEST_DELAY = 1.0
_last_request_time = 0.0


def _rate_limit():
    """确保请求间隔不低于 REQUEST_DELAY"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()


def _fetch_json(path: str, params: str = "") -> Optional[Dict]:
    """
    从 DBLP 获取 JSON，自动 fallback 到镜像站。

    Args:
        path: API 路径（如 /search/publ/api）
        params: URL 查询参数字符串

    Returns:
        JSON 解析后的字典，失败返回 None
    """
    url_suffix = f"{path}?{params}" if params else path

    for host in DBLP_HOSTS:
        _rate_limit()
        url = f"{host}{url_suffix}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, json.JSONDecodeError):
            continue

    return None


def _fetch_text(path: str) -> Optional[str]:
    """
    从 DBLP 获取纯文本（BibTeX），自动 fallback 到镜像站。

    Args:
        path: 资源路径（如 /rec/conf/nips/VaswaniSPUJGKP17.bib）

    Returns:
        文本内容，失败返回 None
    """
    for host in DBLP_HOSTS:
        _rate_limit()
        url = f"{host}{path}"
        try:
            req = Request(url)
            with urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8").strip()
        except (URLError, HTTPError):
            continue

    return None


def _normalize_authors(authors_raw) -> List[str]:
    """
    规范化 DBLP 作者字段。

    DBLP API 特殊行为：单作者时 authors.author 返回 dict 而非 list。
    """
    if authors_raw is None:
        return []
    author = authors_raw.get("author", [])
    if isinstance(author, dict):
        author = [author]
    return [a.get("text", a.get("@text", "")) if isinstance(a, dict) else str(a)
            for a in author]


def _normalize_hit(hit: Dict) -> Dict[str, Any]:
    """
    将 DBLP hit 转为统一的论文字典格式。

    Returns:
        {title, authors, year, venue, dblp_key, dblp_url, doi, type}
    """
    info = hit.get("info", {})
    title = info.get("title", "").rstrip(".")  # DBLP 标题末尾常带句号
    authors = _normalize_authors(info.get("authors"))
    year = info.get("year")
    venue = info.get("venue", "")
    dblp_key = info.get("key", "")        # e.g. "conf/nips/VaswaniSPUJGKP17"
    dblp_url = info.get("url", "")         # e.g. "https://dblp.org/rec/conf/nips/..."
    doi = info.get("doi", "")
    pub_type = info.get("type", "")

    return {
        "title": title,
        "authors": authors,
        "year": int(year) if year and year.isdigit() else year,
        "venue": venue,
        "dblp_key": dblp_key,
        "dblp_url": dblp_url,
        "doi": doi,
        "type": pub_type,
    }


def search_dblp(query: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    通用 DBLP 文献搜索。

    Args:
        query: 搜索关键词
        limit: 返回条数上限（DBLP 最多 1000）
        offset: 起始偏移

    Returns:
        {"data": [...], "total": N, "source": "dblp"}，失败返回含 error 字段
    """
    encoded = quote_plus(query)
    params = f"q={encoded}&format=json&h={limit}&f={offset}"
    result = _fetch_json("/search/publ/api", params)

    if result is None:
        return {"error": "DBLP API unreachable", "data": None}

    hits_wrapper = result.get("result", {}).get("hits", {})
    total = int(hits_wrapper.get("@total", 0))
    hits = hits_wrapper.get("hit", [])

    papers = [_normalize_hit(h) for h in hits]

    return {"data": papers, "total": total, "source": "dblp"}


def get_dblp_bibtex(dblp_key: str) -> Optional[str]:
    """
    通过 DBLP key 获取人工审核的 BibTeX。

    Args:
        dblp_key: DBLP key，如 "conf/nips/VaswaniSPUJGKP17"

    Returns:
        BibTeX 字符串，失败返回 None
    """
    if not dblp_key:
        return None
    # 去掉可能的前缀 URL
    dblp_key = dblp_key.replace("https://dblp.org/rec/", "").replace("https://dblp.uni-trier.de/rec/", "")
    # 去掉可能的 .html 后缀
    dblp_key = dblp_key.rstrip("/").removesuffix(".html")

    bib = _fetch_text(f"/rec/{dblp_key}.bib")
    if bib and bib.startswith("@"):
        return bib
    return None


def search_dblp_by_title(title: str) -> Optional[Dict[str, Any]]:
    """
    按标题精确查找 DBLP 条目，返回最佳匹配。

    使用标题全文作为查询，取第一条结果并验证标题相似度。

    Args:
        title: 论文完整标题

    Returns:
        最佳匹配的论文字典（含 dblp_key），无匹配返回 None
    """
    if not title:
        return None

    clean_title = title.strip().rstrip(".")
    result = search_dblp(clean_title, limit=20)
    if not result.get("data"):
        return None

    # 标题模糊匹配：比较小写化、去标点后的标题
    def _simplify(s: str) -> str:
        return " ".join("".join(c.lower() for c in s if c.isalnum() or c == " ").split())

    query_simplified = _simplify(clean_title)

    best = None
    for paper in result["data"]:
        paper_simplified = _simplify(paper.get("title", ""))
        # 完全匹配 → 立即返回
        if query_simplified == paper_simplified:
            return paper
        # 论文标题是查询的子串（处理查询含副标题的情况），但不能反过来
        # 反过来意味着论文标题比查询更长，是不同的论文
        # 长度至少 80% 才算匹配，避免短标题误匹配
        if not best and paper_simplified in query_simplified:
            if len(paper_simplified) >= len(query_simplified) * 0.8:
                best = paper

    return best


def get_bibtex_by_title(title: str) -> Optional[str]:
    """
    标题 → DBLP 搜索 → DBLP Key → BibTeX，一步到位。

    这是与 doi_to_bibtex.py 集成的主入口。

    Args:
        title: 论文完整标题

    Returns:
        DBLP 人工审核的 BibTeX 字符串，失败返回 None
    """
    paper = search_dblp_by_title(title)
    if paper and paper.get("dblp_key"):
        return get_dblp_bibtex(paper["dblp_key"])
    return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DBLP Search")
    parser.add_argument("query", nargs="*", default=["Attention", "Is", "All", "You", "Need"])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    query = " ".join(args.query)

    print(f"=== DBLP Search: {query} ===\n")

    # 1. 通用搜索
    results = search_dblp(query, limit=args.limit)
    if results.get("data"):
        print(f"Found {results['total']} results (showing top {len(results['data'])})\n")
        for i, p in enumerate(results["data"], 1):
            authors_str = ", ".join(p["authors"][:3])
            if len(p["authors"]) > 3:
                authors_str += " et al."
            print(f"{i}. {p['title']}")
            print(f"   Year: {p['year']} | Venue: {p['venue']}")
            print(f"   DBLP Key: {p['dblp_key']}")
            print(f"   DOI: {p['doi'] or 'N/A'}")
            print(f"   Authors: {authors_str}")
            print()
    else:
        print(f"No results or error: {results.get('error', 'unknown')}")

    # 2. 按标题精确查找 + BibTeX
    print("=== Title Lookup + BibTeX ===\n")
    bib = get_bibtex_by_title(query)
    if bib:
        print(bib)
    else:
        print("No DBLP BibTeX found for this title.")
