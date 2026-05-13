import os
import time
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
if not HEYGEN_API_KEY:
    raise RuntimeError("HEYGEN_API_KEY not found in .env file.")

AVATAR_IMAGE_PATH = "cartoon_output.png"   # The cartoonized avatar image
OUTPUT_VIDEO_FILE = "comedy_video.mp4"     # Where to save the final video

UPLOAD_URL       = "https://upload.heygen.com/v1/asset"
AVG_GROUP_URL    = "https://api.heygen.com/v2/photo_avatar/avatar_group/create"
AVG_LIST_URL     = "https://api.heygen.com/v2/avatar_group.list"
AVG_LOOKS_URL    = "https://api.heygen.com/v2/avatar_group/{group_id}/avatars"
GENERATE_URL     = "https://api.heygen.com/v2/video/generate"
STATUS_URL       = "https://api.heygen.com/v1/video_status.get"
VOICES_URL       = "https://api.heygen.com/v2/voices"

BASE_HEADERS = {"x-api-key": HEYGEN_API_KEY}

# ─────────────────────────────────────────────
# Stand-up comedy script (~20 seconds of speech)
# Punchy, natural pauses for expressive TTS delivery
# ─────────────────────────────────────────────
COMEDY_SCRIPT = (
    "People always ask me: do you ever forget your jokes on stage? "
    "I said, YES! Once I forgot a joke so bad, "
    "I just stood there smiling for 30 seconds... "
    "and STILL got more laughs than my opening line. "
    "My therapist says I use humor to avoid my problems. "
    "I said... yeah, and your POINT is? "
    "Look, I'm a comedian. I don't have problems. "
    "I have MATERIAL."
)

# ─────────────────────────────────────────────
# Step 1 — Upload the cartoon avatar image
# Returns the asset URL (used as image_key)
# ─────────────────────────────────────────────
def upload_avatar_image(image_path: str) -> str:
    """
    Uploads the image as raw binary to HeyGen.
    Returns the image URL/key for avatar group creation.
    """
    print(f"[1/5] Uploading avatar image: {image_path}")

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Avatar image not found: {image_path}")

    with open(image_path, "rb") as f:
        binary_data = f.read()

    headers = {
        **BASE_HEADERS,
        "Content-Type": "image/png",
    }

    response = requests.post(UPLOAD_URL, headers=headers, data=binary_data)

    if response.status_code != 200:
        raise RuntimeError(f"Image upload failed [{response.status_code}]: {response.text}")

    resp_data = response.json().get("data", {})

    # HeyGen upload returns: id, url, image_key (path-style: "image/ID/original.png")
    asset_id  = resp_data.get("id") or resp_data.get("asset_id")
    image_key = resp_data.get("image_key")  # This is what avatar_group/create needs
    asset_url = resp_data.get("url")

    if not image_key:
        # Fallback: construct it from the id if not returned
        image_key = f"image/{asset_id}/original.png"

    print(f"    ✓ Asset uploaded. ID: {asset_id}")
    print(f"    ✓ image_key: {image_key}")
    return image_key   # Return the path-style image_key for avatar group creation


# ─────────────────────────────────────────────
# Step 2 — Create a Photo Avatar Group
# This registers the photo as an avatar
# ─────────────────────────────────────────────
def create_avatar_group(image_key: str) -> str:
    """
    Creates a HeyGen Photo Avatar Group from the uploaded image.
    Returns the group_id.
    """
    print("[2/5] Creating photo avatar group...")

    headers = {
        **BASE_HEADERS,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "name": "Comedian Avatar",
        "image_key": image_key,
    }

    response = requests.post(AVG_GROUP_URL, json=payload, headers=headers)

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Avatar group creation failed [{response.status_code}]: {response.text}")

    data = response.json().get("data", {})
    group_id = data.get("group_id") or data.get("id")

    if not group_id:
        raise RuntimeError(f"Could not parse group_id: {data}")

    print(f"    ✓ Avatar group created. Group ID: {group_id}")
    return group_id


# ─────────────────────────────────────────────
# Step 3 — Get the talking_photo_id from group
# ─────────────────────────────────────────────
def get_talking_photo_id(group_id: str, max_wait: int = 120) -> str:
    """
    Polls the avatar group's looks until the photo avatar is ready.
    Returns the talking_photo_id (avatar look ID).
    """
    print(f"[3/5] Waiting for avatar to be ready (group: {group_id})...")

    looks_url = AVG_LOOKS_URL.format(group_id=group_id)
    headers   = {**BASE_HEADERS, "Accept": "application/json"}

    elapsed = 0
    poll_interval = 8

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        response = requests.get(looks_url, headers=headers)

        if response.status_code != 200:
            print(f"    [{elapsed}s] Status check failed: {response.text}")
            continue

        data    = response.json().get("data", {})
        avatars = data.get("avatar_list") or data.get("looks") or data.get("avatars") or []

        if avatars:
            av = avatars[0]
            # The look ID is the talking_photo_id
            look_id = av.get("avatar_id") or av.get("look_id") or av.get("id")
            status  = av.get("status", "unknown")
            print(f"    [{elapsed}s] Avatar status: {status} | ID: {look_id}")

            if status in ("completed", "active", "ready", "trained"):
                print(f"    ✓ talking_photo_id: {look_id}")
                return look_id
        else:
            print(f"    [{elapsed}s] No avatars in group yet, waiting...")

    raise TimeoutError(f"Avatar not ready after {max_wait} seconds.")


# ─────────────────────────────────────────────
# Step 4 — Pick best comedian voice
# ─────────────────────────────────────────────
def pick_comedian_voice() -> str:
    """
    Queries /v2/voices for an energetic male English voice.
    Falls back to a reliable built-in voice ID.
    """
    print("[4/5] Selecting comedian voice...")

    # Matthew – confident, energetic HeyGen built-in voice
    FALLBACK_VOICE_ID = "2d5b0e6cf36f460aa7fc47e3eee4ba54"

    try:
        response = requests.get(VOICES_URL, headers=BASE_HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"    ⚠ Could not fetch voices. Using fallback.")
            return FALLBACK_VOICE_ID

        voices = response.json().get("data", {}).get("voices", [])
        if not voices:
            print("    ⚠ No voices returned. Using fallback.")
            return FALLBACK_VOICE_ID

        # Prefer expressive/energetic male English voices
        priority_keywords = ["expressive", "energetic", "lively", "confident", "friendly"]
        male_english = [
            v for v in voices
            if str(v.get("gender", "")).lower() == "male"
            and "en" in str(v.get("locale", v.get("language", ""))).lower()
        ]

        for keyword in priority_keywords:
            for v in male_english:
                name = str(v.get("display_name", v.get("name", ""))).lower()
                if keyword in name:
                    vid = v.get("voice_id") or v.get("id")
                    print(f"    ✓ Voice: {v.get('display_name', vid)} ({vid})")
                    return vid

        if male_english:
            v   = male_english[0]
            vid = v.get("voice_id") or v.get("id")
            print(f"    ✓ Voice: {v.get('display_name', vid)} ({vid})")
            return vid

    except Exception as e:
        print(f"    ⚠ Voice fetch error: {e}. Using fallback.")

    print(f"    ✓ Fallback voice: {FALLBACK_VOICE_ID}")
    return FALLBACK_VOICE_ID


# ─────────────────────────────────────────────
# Step 5 — Submit video generation request
# ─────────────────────────────────────────────
def generate_video(talking_photo_id: str, voice_id: str) -> str:
    """
    Submits the HeyGen video generation request.
    Returns the video_id for polling.
    """
    print("[5/5] Submitting video generation request...")

    headers = {
        **BASE_HEADERS,
        "Content-Type": "application/json",
    }

    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "talking_photo",
                    "talking_photo_id": talking_photo_id,
                    "talking_photo_style": "square",    # Clean presenter crop
                    "talking_style": "expressive",      # Expressive for comedy
                    "expression": "happy",              # Comedian energy
                    "gesture": True,                    # Enable natural body gestures
                },
                "voice": {
                    "type": "text",
                    "input_text": COMEDY_SCRIPT,
                    "voice_id": voice_id,
                    "speed": 1.05,                      # Slightly punchy comedy pace
                    "voice_settings": {
                        "emotion": "Excited"            # Excited delivery
                    }
                },
                "background": {
                    "type": "color",
                    "value": "#1a1a2e"                  # Deep dark blue — comedy stage feel
                }
            }
        ],
        "dimension": {
            "width": 1280,
            "height": 720
        },
        "caption": False
    }

    response = requests.post(GENERATE_URL, json=payload, headers=headers)

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Video generation failed [{response.status_code}]: {response.text}")

    data = response.json()
    video_id = data.get("data", {}).get("video_id")
    if not video_id:
        raise RuntimeError(f"Could not parse video_id: {data}")

    print(f"    ✓ Generation started. video_id: {video_id}")
    return video_id


# ─────────────────────────────────────────────
# Poll and Download
# ─────────────────────────────────────────────
def wait_and_download(video_id: str, output_path: str, max_wait: int = 600) -> None:
    """
    Polls HeyGen for video completion and downloads the file.
    """
    print(f"\n⏳ Rendering video... (video_id: {video_id})")
    print("   Expected time: 1–3 minutes for a ~20s video.\n")

    elapsed       = 0
    poll_interval = 12

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        response = requests.get(
            STATUS_URL,
            params={"video_id": video_id},
            headers=BASE_HEADERS
        )

        if response.status_code != 200:
            print(f"   [{elapsed:>4}s] Status check failed: {response.text}")
            continue

        data   = response.json().get("data", {})
        status = data.get("status", "").lower()
        print(f"   [{elapsed:>4}s] Status: {status}")

        if status == "completed":
            video_url = data.get("video_url") or data.get("url")
            if not video_url:
                raise RuntimeError("Video completed but no video_url returned.")

            print(f"\n📥 Downloading video...")
            vid_response = requests.get(video_url, stream=True)
            with open(output_path, "wb") as f:
                for chunk in vid_response.iter_content(chunk_size=8192):
                    f.write(chunk)

            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"\n✅ Comedy video saved: '{output_path}' ({size_mb:.1f} MB)")
            return

        elif status == "failed":
            error = data.get("error", data.get("message", "Unknown error"))
            raise RuntimeError(f"Video generation failed: {error}")

    raise TimeoutError(f"Video not completed after {max_wait} seconds.")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  HeyGen Stand-up Comedy Video Generator")
    print("=" * 55)
    print(f"  Avatar: {AVATAR_IMAGE_PATH}")
    print(f"  Output: {OUTPUT_VIDEO_FILE}")
    print("=" * 55 + "\n")

    # 1. Upload cartoon avatar image
    image_key = upload_avatar_image(AVATAR_IMAGE_PATH)

    # 2. Register as a HeyGen photo avatar group
    group_id = create_avatar_group(image_key)

    # 3. Get the talking_photo_id from the group
    talking_photo_id = get_talking_photo_id(group_id)

    # 4. Select comedian voice
    voice_id = pick_comedian_voice()

    # 5. Generate the comedy video
    video_id = generate_video(talking_photo_id, voice_id)

    # 6. Wait and download
    wait_and_download(video_id, OUTPUT_VIDEO_FILE)
