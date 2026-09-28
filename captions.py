"""Caption and comment-reply drafting with Claude."""

import os

import anthropic

MODEL = "claude-opus-5-5"

SYSTEM = (
    "You write Instagram copy for a small creator account. Keep it natural and "
    "on-brand, avoid clichés, and match the tone the user asks for. Reply with "
    "only the text to post, with no preamble or quotation marks."
)


def claude_available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _ask(prompt):
    if not claude_available():
        return None
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": "low"},
        # If a request is declined by a safety classifier, retry it on
        # Anthropic's recommended fallback model instead of failing.
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write this one. Try rephrasing.")
    return "".join(b.text for b in response.content if b.type == "text").strip()


def draft_caption(description, tone="friendly", hashtags=True):
    prompt = (
        f"Write an Instagram caption for this post: {description}\n"
        f"Tone: {tone}.\n"
        + ("End with 3-6 relevant hashtags." if hashtags else "Do not use hashtags.")
    )
    text = _ask(prompt)
    if text is None:
        return f"[Demo caption: set ANTHROPIC_API_KEY for real drafts] {description} ✨"
    return text


def draft_reply(post_caption, comment_text, commenter):
    prompt = (
        f"My post's caption: {post_caption!r}\n"
        f"@{commenter} commented: {comment_text!r}\n"
        "Write a short, warm reply (one or two sentences) from me."
    )
    text = _ask(prompt)
    if text is None:
        return f"Thanks so much @{commenter}! 🙌"
    return text
