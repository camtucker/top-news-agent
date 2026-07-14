# Top News Agent

An autonomous agent that runs daily on GitHub Actions, decides which top tech
news stories matter, pulls community discussion on the interesting ones, then
commits a markdown digest to this repo and emails it to you.

Inference is free via GitHub Models using the repo's own built-in token, so the
only credential you manage is a Gmail app password for the email step.

It's a real agent loop, not a single prompt: the model chooses which tools to
call (`get_top_stories`, `get_story_comments`), reads the results, and iterates
until it has enough context to write the digest.

## Deploy

### 1. Create a Gmail app password (2 minutes)

1. Your Google account needs 2-step verification turned on
2. Go to https://myaccount.google.com/apppasswords
3. Create one named "top-news-agent" and copy the 16-character password

### 2. Push the repo

```bash
git init && git add . && git commit -m "deploy top news agent"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/top-news-agent.git
git push -u origin main
```

### 3. Add the two email secrets

In the repo: Settings > Secrets and variables > Actions > New repository secret

| Secret name | Value |
|---|---|
| `MAIL_USERNAME` | your Gmail address (also used as the recipient) |
| `MAIL_APP_PASSWORD` | the 16-character app password from step 1 |

No secret is needed for the AI itself. The workflow's `models: read` permission
lets the built-in `GITHUB_TOKEN` call the GitHub Models inference endpoint.

### 4. First run

Go to the Actions tab, select "Top News Agent", click "Run workflow". Watch the
logs (each tool call prints), then check `digests/` and your inbox.

After that it runs itself every day at 9am ET.

## Run locally (optional)

Locally you'd need a GitHub personal access token exported as `GITHUB_TOKEN`
(the email step only runs in Actions, so local runs just write the file):

```bash
pip install openai
export GITHUB_TOKEN=your_pat
python top_news_agent.py
```

## Notes and swap ideas

- Each run makes roughly 3 to 6 model calls, comfortably inside the free tier's
  daily limits.
- Change `MODEL` in `top_news_agent.py` to try other GitHub Models options.
- Point the tools at a different source (RSS, Reddit, arXiv), or swap the digest
  topic entirely by editing the system prompt.
