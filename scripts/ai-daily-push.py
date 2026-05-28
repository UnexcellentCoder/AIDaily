#!/usr/bin/env python3
"""
AI Daily Push — Extract top 20 AI news from DailyBrief,
generate English markdown with ~100 word summaries per article,
push to GitHub AIDaily repo.
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta

# ─── Config ───
REPORT_TZ = os.environ.get("REPORT_TZ", "Asia/Shanghai")
DAILY_REPORT_DIR = os.path.expanduser("~/DailyBrief/daily_reports")
GIT_DIR = os.path.expanduser("~/AIDaily")
OUTPUT_DIR = os.path.expanduser("~/AIDaily/dailyAIBrief")
TOP_N = 20

# ─── MiniMax API ───
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")

def load_minimax_key():
    """Load MiniMax API key from DailyBrief .env.local if not set."""
    global MINIMAX_API_KEY
    if MINIMAX_API_KEY:
        return
    env_path = os.path.expanduser("~/DailyBrief/.env.local")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("MINIMAX_API_KEY="):
                    MINIMAX_API_KEY = line.split("=", 1)[1].strip()
                elif line.startswith("MINIMAX_BASE_URL="):
                    global MINIMAX_BASE_URL
                    MINIMAX_BASE_URL = line.split("=", 1)[1].strip()

# ─── AI keywords ───
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
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / len(text) > 0.7

def call_minimax(prompt, max_tokens=4000):
    """Call MiniMax API to generate text."""
    load_minimax_key()
    if not MINIMAX_API_KEY:
        return None

    url = f"{MINIMAX_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
    }
    payload = json.dumps({
        "model": "MiniMax-Text-01",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"MiniMax API error: {e}", file=sys.stderr)
        return None

def generate_summaries_with_llm(articles):
    """Use MiniMax to generate ~100 word English summaries for each article."""
    articles_text = []
    for i, a in enumerate(articles, 1):
        title = a.get('title', '').strip()
        excerpt = a.get('excerpt', '').strip()[:300]
        source = a.get('source', '')
        articles_text.append(f"[{i}] Title: {title}\nSource: {source}\nExcerpt: {excerpt}")

    prompt = f"""You are a news editor. For each article below, write a concise English summary of about 100 words.
Keep the original meaning. If the text is in Chinese, translate and summarize into English.
Output ONLY a JSON array of strings, one summary per article, in order.

Articles:
{chr(10).join(articles_text)}

Output format (JSON array only, no markdown):
["summary 1", "summary 2", ...]"""

    result = call_minimax(prompt, max_tokens=6000)
    if not result:
        return None

    # Parse JSON from response
    try:
        # Try to extract JSON array from response
        start = result.find('[')
        end = result.rfind(']') + 1
        if start >= 0 and end > start:
            summaries = json.loads(result[start:end])
            if len(summaries) == len(articles):
                return summaries
    except json.JSONDecodeError:
        pass

    print("Failed to parse LLM summaries", file=sys.stderr)
    return None

def generate_fallback_summary(article):
    """Fallback: use excerpt or title as summary."""
    excerpt = article.get('excerpt', '').strip()
    if is_mostly_english(excerpt) and len(excerpt) > 50:
        return excerpt[:500]
    title = article.get('title', '').strip()
    source = article.get('source', '')
    return f"{title} — {source}"

def generate_summary_of_day(ai_articles):
    """Generate a ~100 word English summary of the whole day."""
    highlights = []
    for a in ai_articles[:6]:
        title = a.get('title', '').strip()
        source = a.get('source', '')
        excerpt = a.get('excerpt', '').strip()
        if is_mostly_english(excerpt) and len(excerpt) > 30:
            highlights.append(excerpt[:120])
        elif is_mostly_english(title):
            highlights.append(f"{title} ({source})")
        else:
            continue
    if not highlights:
        return "Today's top AI news highlights."
    combined = '; '.join(highlights[:5])
    if len(combined) > 600:
        combined = combined[:597] + '...'
    return combined

def generate_markdown(date_str, articles, day_summary, article_summaries):
    lines = [
        f"# 🤖 AI Daily — {date_str}",
        "",
        "## 📝 Summary",
        "",
        day_summary,
        "",
        "---",
        "",
        f"## 🔥 Top {TOP_N} AI News",
        "",
    ]
    for i, a in enumerate(articles):
        source = a.get('source', 'Unknown')
        title = a.get('title', '').strip()
        url = a.get('url', '')
        summary = article_summaries[i] if i < len(article_summaries) else generate_fallback_summary(a)

        lines.append(f"### {i+1}. {title}")
        lines.append("")
        lines.append(f"📰 Source: {source}")
        lines.append("")
        lines.append(summary)
        lines.append("")
        if url:
            lines.append(f"🔗 [Read more]({url})")
            lines.append("")

    lines.append("---")
    lines.append(f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    return '\n'.join(lines)

def push_to_github(date_str, md_content):
    file_path = os.path.join(OUTPUT_DIR, f"{date_str}.md")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    cmds = [
        ['git', 'add', f'dailyAIBrief/{date_str}.md'],
        ['git', 'commit', '-m', f'🤖 AI Daily {date_str}'],
        ['git', 'push', 'origin', 'main'],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, cwd=GIT_DIR, capture_output=True, text=True)
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

    # Generate day summary
    day_summary = generate_summary_of_day(top_articles)

    # Generate per-article summaries via LLM
    print(f"Generating {len(top_articles)} article summaries via MiniMax...", file=sys.stderr)
    article_summaries = generate_summaries_with_llm(top_articles)
    if not article_summaries:
        print("LLM summaries failed, using fallback excerpts", file=sys.stderr)
        article_summaries = [generate_fallback_summary(a) for a in top_articles]

    md = generate_markdown(date_used, top_articles, day_summary, article_summaries)
    success = push_to_github(date_used, md)

    if success:
        print(f"SUCCESS: Pushed {len(top_articles)} AI articles for {date_used} to GitHub")
    else:
        print("ERROR: Failed to push to GitHub", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
