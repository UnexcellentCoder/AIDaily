#!/usr/bin/env python3
"""
AI Daily Push — Extract top 20 AI news from DailyBrief reports,
generate an English markdown file and push to GitHub AIDaily repo.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

# ─── Config ───
REPORT_TZ = os.environ.get("REPORT_TZ", "Asia/Shanghai")
DAILY_REPORT_DIR = os.path.expanduser("~/DailyBrief/daily_reports")
REPO_DIR = os.path.expanduser("~/AIDaily")
TOP_N = 20

# ─── AI keywords for filtering ───
AI_KEYWORDS = [
    'AI', 'ai', '人工智能', '大模型', 'LLM', 'llm', 'AGI', 'agi',
    'GPT', 'gpt', 'Claude', 'claude', 'Gemini', 'gemini', 'DeepSeek', 'deepseek',
    'OpenAI', 'openai', 'Anthropic', 'anthropic', 'ChatGPT', 'chatgpt',
    'Qwen', 'qwen', '通义', '文心', '智谱', 'Mistral', 'Llama', 'llama',
    'Midjourney', 'midjourney', 'Stable Diffusion', 'Sora', 'sora',
    'Copilot', 'copilot', 'Cursor', 'cursor', 'Codex', 'codex',
    '小米mimo', 'MCP', 'mcp', 'Kimi', 'kimi', '豆包',
    '机器学习', '深度学习', '神经网络', 'transformer', 'Transformer',
    'RAG', '向量', 'embedding', 'Agent', 'agent', '训练', '推理',
    '智能体', '多模态', 'token', 'Token', 'prompt', 'Prompt',
    'fine-tune', '微调', 'RLHF', 'DPO',
    '智驾', '自动驾驶', 'FSD',
]

def get_today_str():
    import zoneinfo
    tz = zoneinfo.ZoneInfo(REPORT_TZ)
    return datetime.now(tz).strftime("%Y-%m-%d")

def find_report(date_str):
    path = os.path.join(DAILY_REPORT_DIR, date_str, f"{date_str}-articles.json")
    return path if os.path.exists(path) else None

def is_ai_related(article):
    text = article.get('title', '') + ' ' + article.get('excerpt', '')
    return any(kw in text for kw in AI_KEYWORDS)

def score_article(article):
    title = article.get('title', '')
    excerpt = article.get('excerpt', '')
    score = 0
    for kw in AI_KEYWORDS:
        if kw in title:
            score += 3
        if kw in excerpt:
            score += 1
    return score

def is_mostly_english(text):
    """Check if text is mostly ASCII/English."""
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / len(text) > 0.7

def generate_summary(ai_articles):
    """Build a ~100 word English summary from top articles."""
    highlights = []
    for a in ai_articles[:8]:
        title = a.get('title', '').strip()
        source = a.get('source', '')
        excerpt = a.get('excerpt', '').strip()

        if is_mostly_english(excerpt) and len(excerpt) > 30:
            highlights.append(excerpt[:150])
        elif is_mostly_english(title):
            highlights.append(f"{title} ({source})")
        else:
            # Chinese title/excerpt — skip for English summary
            continue

    if not highlights:
        return "Today's top AI news highlights."

    combined = '; '.join(highlights[:5])
    if len(combined) > 600:
        combined = combined[:597] + '...'
    return combined

def generate_markdown(date_str, articles, summary):
    lines = [
        f"# 🤖 AI Daily — {date_str}",
        "",
        "## 📝 Summary",
        "",
        summary,
        "",
        "---",
        "",
        f"## 🔥 Top {TOP_N} AI News",
        "",
    ]
    for i, a in enumerate(articles, 1):
        source = a.get('source', 'Unknown')
        title = a.get('title', '').strip()
        url = a.get('url', '')
        excerpt = a.get('excerpt', '').strip()
        if len(excerpt) > 300:
            excerpt = excerpt[:297] + '...'
        lines.append(f"### {i}. {title}")
        lines.append("")
        lines.append(f"📰 Source: {source}")
        if excerpt:
            lines.append(f"> {excerpt}")
        lines.append("")
        if url:
            lines.append(f"🔗 [Read more]({url})")
        lines.append("")

    lines.append("---")
    lines.append(f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    return '\n'.join(lines)

def push_to_github(date_str, md_content):
    file_path = os.path.join(REPO_DIR, f"{date_str}.md")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    cmds = [
        ['git', 'add', f'{date_str}.md'],
        ['git', 'commit', '-m', f'🤖 AI Daily {date_str}'],
        ['git', 'push', 'origin', 'main'],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        if result.returncode != 0 and 'nothing to commit' not in result.stderr:
            print(f"Error: {result.stderr}", file=sys.stderr)
            return False
    return True

def main():
    today = get_today_str()
    yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    report_path = find_report(today)
    date_used = today
    if not report_path:
        report_path = find_report(yesterday)
        date_used = yesterday

    if not report_path:
        print(f"NO_REPORT: No report found for {today} or {yesterday}")
        sys.exit(0)

    with open(report_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articles = data.get('articles', [])
    ai_articles = [a for a in articles if is_ai_related(a)]
    for a in ai_articles:
        a['_score'] = score_article(a)
    ai_articles.sort(key=lambda a: a['_score'], reverse=True)
    top_articles = ai_articles[:TOP_N]

    if not top_articles:
        print(f"NO_AI_NEWS: No AI-related articles found in {date_used}")
        sys.exit(0)

    summary = generate_summary(top_articles)
    md = generate_markdown(date_used, top_articles, summary)
    success = push_to_github(date_used, md)

    if success:
        print(f"SUCCESS: Pushed {len(top_articles)} AI articles for {date_used} to GitHub")
    else:
        print("ERROR: Failed to push to GitHub", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
