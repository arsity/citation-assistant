---
description: 使用 DBLP 搜索论文并获取权威 BibTeX（CS/AI 领域首选）
argument-hint: 搜索关键词或论文标题
allowed-tools: Bash
---

# /citation:dblp

使用 DBLP API 搜索学术论文。DBLP 是 CS 领域最权威的文献数据库，其 BibTeX 经人工审核，质量最高。

## 参数

**$ARGUMENTS**: 搜索查询语句或论文标题

可选：使用 `--limit N` 指定返回数量（默认 20）

## 执行

```bash
cd "$HOME/.claude/plugins/marketplaces/citation-assistant/claude-code-plugin" && \
QUERY="$ARGUMENTS"; \
LIMIT=$(echo "$QUERY" | grep -o -- '--limit [0-9]*' | awk '{print $2}'); \
LIMIT=${LIMIT:-20}; \
QUERY=$(echo "$QUERY" | sed 's/ --limit [0-9]*//g'); \
python3 scripts/dblp_search.py "$QUERY" --limit "$LIMIT" 2>&1 | head -100
```

## 输出说明

每条结果包含：
- **Title**: 论文标题
- **Year / Venue**: 发表年份和会议/期刊
- **DBLP Key**: 如 `conf/nips/VaswaniSPUJGKP17`，可直接获取 BibTeX
- **DOI**: 如有

## 获取 DBLP BibTeX

找到目标论文的 DBLP Key 后，可通过以下方式获取人工审核的 BibTeX：

```bash
# 直接 curl
curl -s "https://dblp.org/rec/conf/nips/VaswaniSPUJGKP17.bib"

# 或通过 Python（在插件根目录下）
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from dblp_search import get_dblp_bibtex
print(get_dblp_bibtex('conf/nips/VaswaniSPUJGKP17'))
"
```

## 使用场景

```
# CS/AI 论文搜索
/citation:dblp "transformer attention mechanism"

# 按标题精确查找
/citation:dblp "Attention Is All You Need"

# 限制结果数量
/citation:dblp "graph neural network" --limit 10
```

## 与其他命令的配合

- `/citation:search`: Semantic Scholar 语义搜索（含引用量、h-index）
- `/citation:dblp`: DBLP 搜索（CS 领域权威 BibTeX）
- `/citation:bibtex`: DOI → BibTeX（DBLP 无法覆盖时的 fallback）
