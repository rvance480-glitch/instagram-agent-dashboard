"""Instagram Graph API client, plus a demo client with sample data.

Uses the "Instagram API with Facebook Login" flavour of the Graph API, which
requires a Business or Creator account linked to a Facebook Page.
"""

import time
from datetime import datetime, timedelta, timezone

import requests

MEDIA_FIELDS = (
    "id,caption,media_type,media_url,thumbnail_url,permalink,"
    "timestamp,like_count,comments_count"
)
PROFILE_FIELDS = (
    "username,name,biography,profile_picture_url,"
    "followers_count,follows_count,media_count"
)


class InstagramError(Exception):
    pass


class InstagramClient:
    demo = False

    def __init__(self, access_token, user_id, api_version="v23.0"):
        self.token = access_token
        self.user_id = user_id
        self.base = f"https://graph.facebook.com/{api_version}"

    def _request(self, method, path, **params):
        params["access_token"] = self.token
        resp = requests.request(method, f"{self.base}/{path}", params=params, timeout=30)
        data = resp.json()
        if "error" in data:
            raise InstagramError(data["error"].get("message", str(data["error"])))
        return data

    def profile(self):
        return self._request("GET", self.user_id, fields=PROFILE_FIELDS)

    def recent_media(self, limit=12):
        return self._request(
            "GET", f"{self.user_id}/media", fields=MEDIA_FIELDS, limit=limit
        ).get("data", [])

    def media(self, media_id):
        return self._request("GET", media_id, fields=MEDIA_FIELDS)

    def media_insights(self, media_id):
        """Returns {metric: value}. Not every metric exists for every media type."""
        try:
            data = self._request(
                "GET", f"{media_id}/insights", metric="reach,saved,views"
            ).get("data", [])
        except InstagramError:
            return {}
        return {m["name"]: m["values"][0]["value"] for m in data if m.get("values")}

    def comments(self, media_id):
        return self._request(
            "GET",
            f"{media_id}/comments",
            fields="id,text,username,timestamp,replies{id,text,username,timestamp}",
        ).get("data", [])

    def reply_to_comment(self, comment_id, message):
        return self._request("POST", f"{comment_id}/replies", message=message)

    def publish_image(self, image_url, caption):
        """Two-step publish: create a media container, then publish it."""
        container = self._request(
            "POST", f"{self.user_id}/media", image_url=image_url, caption=caption
        )
        creation_id = container["id"]
        for _ in range(10):
            status = self._request("GET", creation_id, fields="status_code")
            if status.get("status_code") in (None, "FINISHED"):
                break
            if status.get("status_code") == "ERROR":
                raise InstagramError("Instagram could not process the image.")
            time.sleep(3)
        return self._request(
            "POST", f"{self.user_id}/media_publish", creation_id=creation_id
        )


def _ago(**kwargs):
    return (datetime.now(timezone.utc) - timedelta(**kwargs)).strftime(
        "%Y-%m-%dT%H:%M:%S+0000"
    )


class DemoInstagramClient:
    """Stands in for the real API until credentials are configured."""

    demo = True

    def __init__(self):
        self._media = [
            {
                "id": f"demo_{i}",
                "caption": caption,
                "media_type": "IMAGE",
                "media_url": f"https://picsum.photos/seed/igdemo{i}/600/600",
                "permalink": "#",
                "timestamp": _ago(days=i * 2 + 1),
                "like_count": likes,
                "comments_count": 2,
            }
            for i, (caption, likes) in enumerate(
                [
                    ("Golden hour at the pier 🌅 #sunset #coast", 482),
                    ("New drop this Friday. Who's ready? 👀", 351),
                    ("Behind the scenes of today's shoot 📸", 290),
                    ("Coffee first, then everything else ☕", 517),
                    ("Weekend trail run. 12k and counting 🏃", 204),
                    ("Thank you for 10k! Giveaway details below 🎉", 933),
                ]
            )
        ]
        self._comments = {
            m["id"]: [
                {"id": f"{m['id']}_c1", "username": "sam.travels", "text": "Love this! 😍",
                 "timestamp": _ago(hours=5), "replies": {"data": []}},
                {"id": f"{m['id']}_c2", "username": "jordan_k", "text": "Where was this taken?",
                 "timestamp": _ago(hours=2), "replies": {"data": []}},
            ]
            for m in self._media
        }

    def profile(self):
        return {
            "username": "demo_account",
            "name": "Demo Account",
            "biography": "Sample data. Add IG_ACCESS_TOKEN and IG_USER_ID to connect your account.",
            "profile_picture_url": "https://picsum.photos/seed/igdemoavatar/150/150",
            "followers_count": 10342,
            "follows_count": 512,
            "media_count": len(self._media),
        }

    def recent_media(self, limit=12):
        return self._media[:limit]

    def media(self, media_id):
        for m in self._media:
            if m["id"] == media_id:
                return m
        raise InstagramError("Post not found.")

    def media_insights(self, media_id):
        m = self.media(media_id)
        return {"reach": m["like_count"] * 7, "saved": m["like_count"] // 12,
                "views": m["like_count"] * 9}

    def comments(self, media_id):
        return self._comments.get(media_id, [])

    def reply_to_comment(self, comment_id, message):
        for comments in self._comments.values():
            for c in comments:
                if c["id"] == comment_id:
                    reply = {"id": f"{comment_id}_r{len(c['replies']['data'])}",
                             "username": "demo_account", "text": message,
                             "timestamp": _ago(seconds=0)}
                    c["replies"]["data"].append(reply)
                    return {"id": reply["id"]}
        raise InstagramError("Comment not found.")

    def publish_image(self, image_url, caption):
        media = {
            "id": f"demo_{len(self._media)}", "caption": caption, "media_type": "IMAGE",
            "media_url": image_url, "permalink": "#", "timestamp": _ago(seconds=0),
            "like_count": 0, "comments_count": 0,
        }
        self._media.insert(0, media)
        self._comments[media["id"]] = []
        return {"id": media["id"]}
