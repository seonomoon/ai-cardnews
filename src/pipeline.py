import os
import json
import time
import requests
import feedparser
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import anthropic

CONFIG = {
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
    "IG_USER_ID":        os.getenv("IG_USER_ID", ""),
    "IG_ACCESS_TOKEN":   os.getenv("IG_ACCESS_TOKEN", ""),
    "IMGBB_API_KEY":     os.getenv("IMGBB_API_KEY", ""),
    "OUTPUT_DIR": Path("output"),
    "RSS_FEEDS": [
        "https://feeds.feedburner.com/TechCrunch/",
        "https://www.wired.com/feed/rss",
        "https://www.technologyreview.com/feed/",
    ],
    "CARD_WIDTH":  1080,
    "CARD_HEIGHT": 1080,
}

THEMES = [
    {"bg": "#0A0A0F", "accent": "#00F5FF", "text": "#FFFFFF", "sub": "#888888"},
    {"bg": "#0D0D1A", "accent": "#FF3CAC", "text": "#FFFFFF", "sub": "#777777"},
    {"bg": "#050505", "accent": "#39FF14", "text": "#FFFFFF", "sub": "#666666"},
    {"bg": "#0F0A0A", "accent": "#FF6B35", "text": "#FFFFFF", "sub": "#888888"},
]

# ── 1. 뉴스 크롤링 ──────────────────────────────
def fetch_news():
    articles = []
    for url in CONFIG["RSS_FEEDS"]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                articles.append({
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", entry.get("description", ""))[:2000],
                    "source":  feed.feed.get("title", "Tech"),
                })
            if len(articles) >= 3:
                break
        except Exception as e:
            print(f"RSS 오류: {e}")
    print(f"✅ {len(articles)}개 기사 수집")
    return articles[0] if articles else {"title": "AI 최신 트렌드", "summary": "AI 기술이 빠르게 발전하고 있습니다.", "source": "Tech"}

# ── 2. Claude AI 카드뉴스 변환 ─────────────────
def generate_cardnews(article):
    client = anthropic.Anthropic(api_key=CONFIG["ANTHROPIC_API_KEY"])
    prompt = f"""당신은 MZ세대 타겟 AI 인스타그램 계정 전문가입니다.

기사 제목: {article['title']}
기사 내용: {article['summary']}
출처: {article['source']}

인스타그램 10장 카드뉴스로 변환하세요.
규칙:
- 카드1: 후킹 제목 (충격/궁금증 유발, 20자 이내)
- 카드2~9: 핵심 정보 각 1문장 (30자 이내, 이모지 1개)
- 카드10: 팔로우 유도 CTA
- 톤: 친근하고 자극적

JSON만 응답:
{{
  "cards": [
    {{"num": 1, "text": "제목"}},
    {{"num": 2, "text": "정보1"}},
    {{"num": 3, "text": "정보2"}},
    {{"num": 4, "text": "정보3"}},
    {{"num": 5, "text": "정보4"}},
    {{"num": 6, "text": "정보5"}},
    {{"num": 7, "text": "정보6"}},
    {{"num": 8, "text": "정보7"}},
    {{"num": 9, "text": "정보8"}},
    {{"num": 10, "text": "팔로우하면 매일 AI 트렌드 🔔"}}
  ],
  "caption": "인스타 본문 200자",
  "hashtags": ["#AI", "#기술뉴스", "#트렌드", "#인공지능", "#테크"]
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]
    return json.loads(raw.strip())

# ── 3. 카드 이미지 생성 ────────────────────────
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf" if bold else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: continue
    return ImageFont.load_default()

def wrap_text(text, max_chars=14):
    lines = []
    while len(text) > max_chars:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    if text: lines.append(text)
    return lines

def draw_card(card, theme, out_path):
    W, H = CONFIG["CARD_WIDTH"], CONFIG["CARD_HEIGHT"]
    img = Image.new("RGB", (W, H), hex_to_rgb(theme["bg"]))
    draw = ImageDraw.Draw(img)
    accent = hex_to_rgb(theme["accent"])

    # 그라디언트 배경
    for y in range(H):
        ratio = y / H * 0.12
        bg = hex_to_rgb(theme["bg"])
        r = int(bg[0] + (accent[0]-bg[0]) * ratio)
        g = int(bg[1] + (accent[1]-bg[1]) * ratio)
        b = int(bg[2] + (accent[2]-bg[2]) * ratio)
        draw.line([(0,y),(W,y)], fill=(r,g,b))

    # 그리드
    for x in range(0, W, 60):
        draw.line([(x,0),(x,H)], fill=(*accent[:3], 12), width=1)
    for y in range(0, H, 60):
        draw.line([(0,y),(W,y)], fill=(*accent[:3], 12), width=1)

    # 상단 바
    draw.rectangle([(0,0),(W,8)], fill=accent)

    num = card["num"]
    text = card["text"]

    if num == 1:
        # 제목 카드
        draw.text((80,60), "AI TREND", font=get_font(32,True), fill=accent)
        draw.text((80,105), datetime.now().strftime("%Y.%m.%d"), font=get_font(26), fill=hex_to_rgb(theme["sub"]))
        lines = wrap_text(text, 10)
        y = 320
        for line in lines:
            draw.text((80,y), line, font=get_font(80,True), fill=hex_to_rgb(theme["text"]))
            y += 100
        draw.rectangle([(80,H-160),(86,H-90)], fill=accent)
        draw.text((106,H-155), "출처: Tech News", font=get_font(28), fill=hex_to_rgb(theme["sub"]))
        draw.text((W-130,H-70), "1/10", font=get_font(30,True), fill=accent)

    elif num == 10:
        # CTA 카드
        draw.ellipse([(-150,-150),(600,600)], fill=(*accent, 18))
        lines = wrap_text(text, 12)
        y = 360
        for line in lines:
            draw.text((80,y), line, font=get_font(62,True), fill=hex_to_rgb(theme["text"]))
            y += 85
        draw.rounded_rectangle([(80,H-230),(W-80,H-130)], radius=50, fill=accent)
        draw.text((160,H-200), "팔로우하고 매일 트렌드 받기 🔔", font=get_font(36), fill=hex_to_rgb(theme["bg"]))

    else:
        # 내용 카드
        draw.ellipse([(60,140),(200,280)], fill=accent)
        draw.text((95,172), str(num), font=get_font(60,True), fill=hex_to_rgb(theme["bg"]))
        lines = wrap_text(text, 14)
        y = 390
        for line in lines:
            draw.text((80,y), line, font=get_font(58,True), fill=hex_to_rgb(theme["text"]))
            y += 80
        draw.rectangle([(80,H-110),(W-80,H-104)], fill=accent)
        draw.text((W-150,H-75), f"{num}/10", font=get_font(30,True), fill=hex_to_rgb(theme["sub"]))

    img.save(out_path, "PNG", quality=95)

def generate_images(cardnews_data):
    import random
    theme = random.choice(THEMES)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = CONFIG["OUTPUT_DIR"] / ts
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for card in cardnews_data["cards"]:
        out = folder / f"card_{card['num']:02d}.png"
        draw_card(card, theme, out)
        print(f"  📸 카드 {card['num']}/10 생성")
        paths.append(out)
    meta = {
        "timestamp": ts,
        "caption": cardnews_data["caption"],
        "hashtags": cardnews_data["hashtags"],
        "image_paths": [str(p) for p in paths],
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"✅ 이미지 저장: {folder}")
    return paths, meta

# ── 4. 이미지 호스팅 ───────────────────────────
def upload_image(image_path):
    import base64
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": CONFIG["IMGBB_API_KEY"], "image": b64},
        timeout=30
    )
    return resp.json()["data"]["url"]

# ── 5. 인스타 업로드 ───────────────────────────
def upload_instagram(image_paths, meta):
    BASE = "https://graph.facebook.com/v18.0"
    uid = CONFIG["IG_USER_ID"]
    token = CONFIG["IG_ACCESS_TOKEN"]

    print("☁️ 이미지 호스팅 중...")
    urls = []
    for i, p in enumerate(image_paths):
        url = upload_image(p)
        urls.append(url)
        print(f"  {i+1}/10 업로드")
        time.sleep(1)

    print("📸 인스타 컨테이너 생성 중...")
    children = []
    for url in urls:
        r = requests.post(f"{BASE}/{uid}/media",
            params={"image_url": url, "is_carousel_item": True, "access_token": token})
        children.append(r.json()["id"])
        time.sleep(2)

    caption = meta["caption"] + "\n\n" + " ".join(meta["hashtags"])
    r = requests.post(f"{BASE}/{uid}/media",
        params={"media_type": "CAROUSEL", "children": ",".join(children),
                "caption": caption, "access_token": token})
    carousel_id = r.json()["id"]

    time.sleep(5)
    r = requests.post(f"{BASE}/{uid}/media_publish",
        params={"creation_id": carousel_id, "access_token": token})
    post_id = r.json()["id"]
    print(f"✅ 게시 완료! Post ID: {post_id}")
    return post_id

# ── 메인 ───────────────────────────────────────
def main():
    print("🚀 AI 카드뉴스 파이프라인 시작\n")

    print("📰 뉴스 크롤링...")
    article = fetch_news()

    print("🧠 Claude AI 변환...")
    cardnews = generate_cardnews(article)

    print("🎨 이미지 생성...")
    paths, meta = generate_images(cardnews)

    if CONFIG["IG_USER_ID"] and CONFIG["IG_ACCESS_TOKEN"] and CONFIG["IMGBB_API_KEY"]:
        print("📤 인스타 업로드...")
        upload_instagram(paths, meta)
    else:
        print("⚠️ API 키 미설정 → 이미지만 저장됨")

    print("\n🎉 완료!")

if __name__ == "__main__":
    main()
