"""Flask dashboard for managing an Instagram account via the Meta Graph API."""

import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from captions import claude_available, draft_caption, draft_reply
from instagram import DemoInstagramClient, InstagramClient, InstagramError

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret")

if os.environ.get("IG_ACCESS_TOKEN") and os.environ.get("IG_USER_ID"):
    ig = InstagramClient(
        os.environ["IG_ACCESS_TOKEN"],
        os.environ["IG_USER_ID"],
        os.environ.get("GRAPH_API_VERSION", "v23.0"),
    )
else:
    ig = DemoInstagramClient()

# Instagram's API has no native scheduling, so scheduled posts are kept in a
# local JSON file and published by a background thread when they come due.
SCHEDULE_FILE = Path(os.environ.get("SCHEDULE_FILE", "data/scheduled.json"))
_schedule_lock = threading.Lock()


def load_schedule():
    if not SCHEDULE_FILE.exists():
        return []
    return json.loads(SCHEDULE_FILE.read_text())


def save_schedule(items):
    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_FILE.write_text(json.dumps(items, indent=2))


def publish_due_posts():
    with _schedule_lock:
        items = load_schedule()
        now = datetime.now().isoformat(timespec="minutes")
        for item in items:
            if item["status"] == "pending" and item["publish_at"] <= now:
                try:
                    result = ig.publish_image(item["image_url"], item["caption"])
                    item.update(status="published", media_id=result.get("id"))
                except (InstagramError, OSError) as e:
                    item.update(status="failed", error=str(e))
        save_schedule(items)


def scheduler_loop():
    while True:
        try:
            publish_due_posts()
        except Exception as e:  # keep the thread alive no matter what
            app.logger.exception("Scheduler error: %s", e)
        time.sleep(60)


@app.context_processor
def inject_status():
    return {"demo_mode": ig.demo, "claude_enabled": claude_available()}


@app.errorhandler(InstagramError)
def handle_instagram_error(e):
    return render_template("error.html", message=str(e)), 502


@app.route("/")
def dashboard():
    profile = ig.profile()
    media = ig.recent_media()
    total_likes = sum(m.get("like_count", 0) for m in media)
    total_comments = sum(m.get("comments_count", 0) for m in media)
    avg_engagement = (
        (total_likes + total_comments) / len(media) / profile["followers_count"] * 100
        if media and profile.get("followers_count")
        else 0
    )
    return render_template(
        "dashboard.html",
        profile=profile,
        media=media,
        total_likes=total_likes,
        total_comments=total_comments,
        avg_engagement=avg_engagement,
    )


@app.route("/post/<media_id>")
def post_detail(media_id):
    return render_template(
        "post.html",
        post=ig.media(media_id),
        insights=ig.media_insights(media_id),
        comments=ig.comments(media_id),
    )


@app.post("/comment/<comment_id>/reply")
def reply(comment_id):
    message = request.form.get("message", "").strip()
    if message:
        ig.reply_to_comment(comment_id, message)
        flash("Reply posted.")
    return redirect(url_for("post_detail", media_id=request.form["media_id"]))


@app.post("/api/draft-reply")
def api_draft_reply():
    body = request.get_json(force=True)
    try:
        text = draft_reply(body.get("caption", ""), body["comment"], body["username"])
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(text=text)


@app.route("/compose", methods=["GET", "POST"])
def compose():
    if request.method == "POST":
        image_url = request.form["image_url"].strip()
        caption = request.form["caption"].strip()
        publish_at = request.form.get("publish_at", "").strip()
        if not image_url.startswith("https://"):
            flash("The image must be a public https:// URL. Instagram fetches it directly.")
            return render_template("compose.html", form=request.form)
        if publish_at:
            with _schedule_lock:
                items = load_schedule()
                items.append({
                    "id": uuid.uuid4().hex[:8], "image_url": image_url,
                    "caption": caption, "publish_at": publish_at, "status": "pending",
                })
                save_schedule(items)
            flash(f"Scheduled for {publish_at.replace('T', ' ')}.")
            return redirect(url_for("schedule"))
        ig.publish_image(image_url, caption)
        flash("Published!")
        return redirect(url_for("dashboard"))
    return render_template("compose.html", form={})


@app.post("/api/draft-caption")
def api_draft_caption():
    body = request.get_json(force=True)
    try:
        text = draft_caption(
            body["description"], body.get("tone", "friendly"), body.get("hashtags", True)
        )
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(text=text)


@app.route("/schedule")
def schedule():
    items = sorted(load_schedule(), key=lambda i: i["publish_at"])
    return render_template("schedule.html", items=items)


@app.post("/schedule/<item_id>/cancel")
def cancel_scheduled(item_id):
    with _schedule_lock:
        save_schedule([i for i in load_schedule() if i["id"] != item_id])
    flash("Scheduled post removed.")
    return redirect(url_for("schedule"))


def start_scheduler():
    threading.Thread(target=scheduler_loop, daemon=True).start()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG") == "1"
    # With the debug reloader, only start the scheduler in the child process.
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_scheduler()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=debug)
