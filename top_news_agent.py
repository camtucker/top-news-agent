"""
Top News Agent.

An autonomous daily agent: the model decides which tools to call
(top stories, comments), reads the results, and keeps going until
it has enough to write a digest of the day's top tech news.

Runs free on GitHub Models using the repo's built-in GITHUB_TOKEN,
so there is no separate API signup at all.
"""

import json
import os
import urllib.request
from datetime import date, timezone, datetime
from pathlib import Path

from openai import OpenAI

MODEL = "openai/gpt-4o-mini"
HN_API = "https://hacker-news.firebaseio.com/v0"

client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=os.environ["GITHUB_TOKEN"],
)


# ---------- Tools ----------

def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def get_top_stories(limit: int = 10) -> list[dict]:
    """Fetch the current top HN stories (id, title, score, url)."""
    ids = _get_json(f"{HN_API}/topstories.json")[: min(int(limit), 20)]
    stories = []
    for sid in ids:
        s = _get_json(f"{HN_API}/item/{sid}.json") or {}
        stories.append(
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "score": s.get("score"),
                "comments": s.get("descendants", 0),
                "url": s.get("url", f"https://news.ycombinator.com/item?id={sid}"),
            }
        )
    return stories


def get_story_comments(story_id: int, limit: int = 5) -> list[str]:
    """Fetch the text of the top comments on a story."""
    s = _get_json(f"{HN_API}/item/{int(story_id)}.json") or {}
    out = []
    for cid in (s.get("kids") or [])[: min(int(limit), 8)]:
        c = _get_json(f"{HN_API}/item/{cid}.json") or {}
        text = c.get("text", "")
        if text:
            out.append(text[:500])
    return out


AVAILABLE_TOOLS = {
    "get_top_stories": get_top_stories,
    "get_story_comments": get_story_comments,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_top_stories",
            "description": "Get the current top Hacker News stories with titles, scores, and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many stories to fetch (max 20)."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_story_comments",
            "description": "Get top comment text for a specific story id, useful for gauging discussion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "story_id": {"type": "integer"},
                    "limit": {"type": "integer", "description": "How many top comments to fetch (max 8)."},
                },
                "required": ["story_id"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are an autonomous research agent that produces a daily tech digest.

Process:
1. Fetch the top Hacker News stories.
2. Pick the 5 most interesting ones, favoring AI, dev tools, and startups.
3. For 2 or 3 of your picks, pull comments to capture what the discussion is about.
4. Write a markdown digest: a title with today's date, then for each story a bolded
   headline linked to its URL, a 2 sentence summary of why it matters, and where you
   read comments, one line on the community's take.

When you are done researching, reply with ONLY the final markdown digest, nothing else."""


# ---------- Agent loop ----------

def run_agent(max_turns: int = 10) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Create today's digest. Today is {date.today().isoformat()}."},
    ]

    for turn in range(max_turns):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            temperature=0.4,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        messages.append(msg)
        for tc in msg.tool_calls:
            fn = AVAILABLE_TOOLS[tc.function.name]
            args = json.loads(tc.function.arguments or "{}")
            print(f"[turn {turn}] tool call: {tc.function.name}({args})")
            try:
                result = fn(**args)
            except Exception as e:
                result = {"error": str(e)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result)[:6000],
                }
            )

    raise RuntimeError("Agent hit max turns without finishing.")


if __name__ == "__main__":
    digest = run_agent()
    out_dir = Path("digests")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    content = digest + f"\n\n---\n*Generated autonomously by Top News Agent at {stamp}*\n"

    dated_path = out_dir / f"{date.today().isoformat()}.md"
    dated_path.write_text(content)
    (out_dir / "latest.md").write_text(content)  # stable path for the email step
    print(f"Wrote {dated_path} and digests/latest.md")
