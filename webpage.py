from flask import Flask, render_template, request, redirect, url_for
import os, json, shutil
from datetime import datetime



app = Flask(__name__)

# Upload folder
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# JSON files
LATEST_FILE = 'posts.json'          # always overwritten
HISTORY_FILE = 'posts_history.json' # append-only

# Initialize files if not exist
for file in [LATEST_FILE, HISTORY_FILE]:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump([], f)

# Allowed extensions
ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_VID = {'mp4', 'avi', 'mov'}

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

def save_latest(post_data):
    """Override latest post file with only this post."""
    with open(LATEST_FILE, 'w') as f:
        json.dump([post_data], f, indent=4)

def append_history(post_data):
    """Append post to history file."""
    with open(HISTORY_FILE, 'r+') as f:
        data = json.load(f)
        data.append(post_data)
        f.seek(0)
        json.dump(data, f, indent=4)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        priority = request.form.get('priority', 'ordinary')
        text_content = request.form.get('text_content', '')

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        post_folder = os.path.join(UPLOAD_FOLDER, f"post_{timestamp}")
        os.makedirs(post_folder, exist_ok=True)

        # Save text file
        if text_content.strip():
            with open(os.path.join(post_folder, "post.txt"), 'w') as f:
                f.write(f"[{priority.upper()}] {text_content}")

        # Get files
        image = request.files.get('image')
        video = request.files.get('video')

        # ✅ Validation: only one media type
        if image and video:
            return "You can upload either an image OR a video, not both.", 400

        media_path = None

        # Save image
        if image and allowed_file(image.filename, ALLOWED_IMG):
            media_path = f"uploads/post_{timestamp}/image_{image.filename}"
            image.save(os.path.join(post_folder, f"image_{image.filename}"))

        # Save video
        elif video and allowed_file(video.filename, ALLOWED_VID):
            media_path = f"uploads/post_{timestamp}/video_{video.filename}"
            video.save(os.path.join(post_folder, f"video_{video.filename}"))

        # Build post entry
        post_entry = {
            "status": priority,
            "text": text_content.strip(),
            "media_path": media_path,
            "timestamp": timestamp
        }

        # ✅ Save latest (override) and append history
        save_latest(post_entry)
        append_history(post_entry)

        return redirect(url_for('index'))

    # Build posts list for UI
    posts = []
    for post in sorted(os.listdir(UPLOAD_FOLDER), reverse=True):
        post_path = os.path.join(UPLOAD_FOLDER, post)
        if os.path.isdir(post_path):
            post_data = {"name": post, "text": None, "images": [], "videos": []}

            txt_file = os.path.join(post_path, "post.txt")
            if os.path.exists(txt_file):
                with open(txt_file) as f:
                    post_data["text"] = f.read()

            for file in os.listdir(post_path):
                if file.lower().endswith(tuple(ALLOWED_IMG)):
                    post_data["images"].append(f"uploads/{post}/{file}")
                elif file.lower().endswith(tuple(ALLOWED_VID)):
                    post_data["videos"].append(f"uploads/{post}/{file}")

            posts.append(post_data)

    return render_template('index.html', posts=posts)

@app.route('/delete/<post_name>', methods=['POST'])
def delete_post(post_name):

    # -------------------------
    # 1. Delete post folder
    # -------------------------
    post_folder = os.path.join(UPLOAD_FOLDER, post_name)
    if os.path.exists(post_folder):
        shutil.rmtree(post_folder)

    # Extract timestamp from folder name "post_20250101123045"
    timestamp = post_name.replace("post_", "")

    # -------------------------
    # 2. Delete from posts_history.json
    # -------------------------
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r+') as f:
            data = json.load(f)

            # Keep only entries that are NOT the deleted post
            new_data = [p for p in data if p.get("timestamp") != timestamp]

            f.seek(0)
            f.truncate()  # clear file
            json.dump(new_data, f, indent=4)

    # -------------------------
    # 3. ALSO clean from latest.json if needed
    # -------------------------
    if os.path.exists(LATEST_FILE):
        with open(LATEST_FILE, 'r+') as f:
            data = json.load(f)
            new_data = [p for p in data if p.get("timestamp") != timestamp]

            f.seek(0)
            f.truncate()
            json.dump(new_data, f, indent=4)

    return redirect(url_for('index'))



# if __name__ == '__main__':


#     # Run Flask
#     app.run(host='0.0.0.0', port=5000, debug=True)