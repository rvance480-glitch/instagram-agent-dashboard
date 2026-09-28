# instagram-agent-dashboard

Flask dashboard for managing an Instagram account through the Meta Graph API, with Claude drafting captions and comment replies.

**Features**
- Overview: profile stats, recent posts, likes, comments and engagement rate
- Post detail: reach, saves and views insights, plus comments with replies
- Reply to comments, with an optional reply drafted by Claude
- Publish an image now or schedule it for later
- Draft captions with Claude, with a choice of tone and hashtags

If Instagram credentials aren't set, the app runs in **demo mode** with sample data.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in the values below
python app.py             # http://localhost:5000
```

## Connect your Instagram account

The Graph API only works with **Business or Creator** accounts linked to a Facebook Page.

1. In the Instagram app, go to Settings → Account type and tools and switch to a Professional (Business or Creator) account. Link it to a Facebook Page.
2. At <https://developers.facebook.com/apps>, create an app (type **Business**) and add the **Instagram** product. Choose "API setup with Facebook login".
3. In the [Graph API Explorer](https://developers.facebook.com/tools/explorer/), select your app and generate a User token with these permissions:
   `instagram_basic`, `instagram_manage_comments`, `instagram_manage_insights`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
4. Exchange it for a **long-lived token**, which lasts about 60 days:
   ```
   GET https://graph.facebook.com/v23.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN
   ```
5. Find your **Instagram Business Account ID**:
   ```
   GET https://graph.facebook.com/v23.0/me/accounts?fields=name,instagram_business_account&access_token=LONG_TOKEN
   ```
   Use the `instagram_business_account.id` value. This is not the Page ID.
6. Put `IG_ACCESS_TOKEN` and `IG_USER_ID` in `.env` (or set them as environment variables) and restart the app.

For Claude drafts, also set `ANTHROPIC_API_KEY` (from <https://console.anthropic.com>).

## Notes and limits

- **Publishing needs a public `https://` image URL.** Instagram downloads the image itself, so you can't upload from your computer. JPEG works best. Instagram limits publishing to 50 posts per 24 hours through the API.
- **Scheduling is handled by this app**, not by Instagram. Scheduled posts are stored in `data/scheduled.json` and published by a background check that runs every minute. The app must be running when a post is due.
- **Tokens expire.** Long-lived tokens last about 60 days. If the dashboard shows an auth error, generate a new token.
- Keep `.env` private. It's already listed in `.gitignore`.
