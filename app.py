import csv
import tempfile
import requests
import os
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

def cluster_keywords_simple(keywords):
    clusters = {}
    for kw in keywords:
        prefix = kw[0] if kw else "misc"
        if prefix not in clusters:
            clusters[prefix] = []
        clusters[prefix].append(kw)
    msg_lines = []
    for key in clusters:
        msg_lines.append(f"Group '{key}': {', '.join(clusters[key])}")
    return "\n".join(msg_lines), clusters

def get_outline_for_keyword(keyword):
    return f"Outline for '{keyword}':\n- Introduction\n- Key Points\n- Conclusion"

def generate_post_idea(keyword):
    return f"Post idea for '{keyword}': How {keyword} impacts your business."

@app.command("/hello")
def say_hello(ack, body, respond):
    ack()
    user = body.get('user_name', 'there')
    respond(f"Hello {user}! 👋 Your bot is working!")

@app.command("/keywords")
def handle_keywords(ack, body, say):
    ack()
    keywords_raw = body.get('text', '')
    keywords = [k.strip().lower() for k in keywords_raw.replace(',', '\n').split('\n') if k.strip()]
    keywords = list(set(keywords))
    say(f"\nYou provided these keywords: {', '.join(keywords)}")

@app.event("file_shared")
def handle_file_shared(event, client, say):
    file_id = event.get("file_id") or event.get("file", {}).get("id")
    file_info = client.files_info(file=file_id)
    url = file_info["file"]["url_private_download"]
    headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}

    with requests.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
            temp_path = f.name

    keywords = []
    with open(temp_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            for cell in row:
                cell = cell.strip().lower()
                if cell and cell not in keywords:
                    keywords.append(cell)
    os.remove(temp_path)

    groups_msg, clusters = cluster_keywords_simple(keywords)

    outline_msgs = []
    idea_msgs = []
    for key, kws in clusters.items():
        if kws:
            outline_msgs.append(get_outline_for_keyword(kws[0]))
            idea_msgs.append(generate_post_idea(kws[0]))

    say(
        f"*Extracted and grouped your keywords:*\n{groups_msg}"
        + "\n\n*Suggested Outlines:*\n" + "\n\n".join(outline_msgs)
        + "\n\n*Suggested Post Ideas:*\n" + "\n\n".join(idea_msgs)
    )

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(port=3000)
