#!/usr/bin/env python3
"""
Citation Assistant CLI
提供命令行接口供 Claude Code 调用

用法示例:
    python cli.py search "attention mechanism transformer" --limit 10
    python cli.py search "LLM irrelevant context" --year 2020- --top 3
    python cli.py quality '{"title": "...", "venue": "ICML", ...}'
    python cli.py check-key
"""

import sys
import os
import json
import argparse

# 确保 skill 目录在 Python 路径中
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

# 将 scripts 目录也加入路径
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# 现在可以安全导入
from s2_search import search_with_fallback, search_papers, check_api_key, batch_get_authors
from quality_ranker import batch_quality_report, get_paper_quality_report, CCFLookup, ImpactFactorLookup
from doi_to_bibtex import doi_to_bibtex


def cmd_search(args):
    """执行文献搜索"""
    result = search_with_fallback(
        query=args.query,
        limit=args.limit,
        year_range=args.year
    )

    if result.get("error"):
        print(json.dumps({"error": result["error"]}, ensure_ascii=False))
        return 1

    papers = result.get("data", [])
    if not papers:
        print(json.dumps({"message": "No results found", "data": []}, ensure_ascii=False))
        return 0

    # 如果请求了质量报告
    if args.top:
        reports = batch_quality_report(papers, top_n=args.top)
        output = {
            "source": result.get("source", "semantic_scholar"),
            "total": len(papers),
            "top_recommendations": reports
        }
    else:
        # 只返回基本信息
        output = {
            "source": result.get("source", "semantic_scholar"),
            "total": len(papers),
            "papers": papers[:args.limit]
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def cmd_quality(args):
    """评估论文质量"""
    try:
        paper = json.loads(args.paper_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}, ensure_ascii=False))
        return 1

    report = get_paper_quality_report(paper)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_bibtex(args):
    """获取 BibTeX"""
    bibtex = doi_to_bibtex(args.doi)
    if bibtex:
        print(bibtex)
        return 0
    else:
        print(json.dumps({"error": "Failed to fetch BibTeX"}, ensure_ascii=False))
        return 1


def cmd_check_key(args):
    """检查 API Key 配置"""
    is_configured, message = check_api_key()
    print(json.dumps({
        "configured": is_configured,
        "message": message
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_venue(args):
    """查询期刊/会议信息"""
    ccf = CCFLookup()
    if_lookup = ImpactFactorLookup()

    result = {"venue": args.name}

    # CCF 查询
    ccf_info = ccf.lookup_by_venue(args.name)
    if ccf_info:
        result["ccf"] = {
            "rank": ccf_info.get("rank"),
            "field": ccf_info.get("field"),
            "type": ccf_info.get("type"),
            "full_name": ccf_info.get("name")
        }

    # 影响因子查询
    if_info = if_lookup.lookup(args.name)
    if if_info:
        result["impact_factor"] = if_info.get("impact_factor")
        result["jcr_quartile"] = if_info.get("jcr_quartile")
        result["cas_quartile"] = if_info.get("cas_quartile")

    if not ccf_info and not if_info:
        result["message"] = "Venue not found in CCF or Impact Factor databases"

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Citation Assistant CLI - 学术文献引用助手",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索学术文献")
    search_parser.add_argument("query", help="搜索查询（语义化描述）")
    search_parser.add_argument("--limit", type=int, default=20, help="返回结果数量（默认 20）")
    search_parser.add_argument("--year", help="年份范围，如 '2020-' 或 '2018-2024'")
    search_parser.add_argument("--top", type=int, help="只返回排序后的前 N 篇（带质量报告）")
    search_parser.set_defaults(func=cmd_search)

    # quality 命令
    quality_parser = subparsers.add_parser("quality", help="评估论文质量")
    quality_parser.add_argument("paper_json", help="论文信息的 JSON 字符串")
    quality_parser.set_defaults(func=cmd_quality)

    # bibtex 命令
    bibtex_parser = subparsers.add_parser("bibtex", help="通过 DOI 获取 BibTeX")
    bibtex_parser.add_argument("doi", help="论文 DOI")
    bibtex_parser.set_defaults(func=cmd_bibtex)

    # check-key 命令
    check_key_parser = subparsers.add_parser("check-key", help="检查 API Key 配置状态")
    check_key_parser.set_defaults(func=cmd_check_key)

    # venue 命令
    venue_parser = subparsers.add_parser("venue", help="查询期刊/会议信息（CCF/JCR/IF）")
    venue_parser.add_argument("name", help="期刊/会议名称或缩写")
    venue_parser.set_defaults(func=cmd_venue)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
