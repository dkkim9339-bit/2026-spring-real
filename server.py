import json, os, time, re
import urllib.request
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)
DB_FILE = "settings.json"

# 유명한 사이트들은 접속 시간 아끼기 위해 기본 사전에 냅둠
INFERENCE_MAP = {
    "everytime": ["에브리타임", "에타", "everytime.kr"],
    "instagram": ["인스타그램", "인스타", "instagram.com"],
    "youtube": ["유튜브", "유튜", "youtube.com", "youtu.be"],
    "naver": ["네이버", "naver.com"],
    "google": ["구글", "google.com"],
    "teamblind": ["블라인드", "blind", "teamblind.com"],
    "koreapas": ["고파스", "koreapas.com"]
}

# 구형 인코딩(EUC-KR)까지 완벽하게 지원하는 크롤러
def get_website_title(url):
    if not url.startswith('http'):
        url = 'http://' + url
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        response = urllib.request.urlopen(req, timeout=3)
        html_bytes = response.read()
        
        charset = 'utf-8'
        content_type = response.headers.get('Content-Type', '').lower()
        if 'charset=' in content_type:
            charset = content_type.split('charset=')[-1].strip()
        else:
            meta_match = re.search(rb'charset=["\']?([\w-]+)["\']?', html_bytes, re.IGNORECASE)
            if meta_match:
                charset = meta_match.group(1).decode('ascii')
        
        try:
            text = html_bytes.decode(charset)
        except:
            try:
                text = html_bytes.decode('euc-kr')
            except:
                text = html_bytes.decode('utf-8', errors='ignore')
        
        match = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            main_keyword = re.split(r'[|\-:]', title)[0].strip()
            return main_keyword
    except Exception as e:
        print(f"제목 추출 실패: {e}")
        return None
    return None

@app.route("/")
def index(): return send_from_directory(".", "site_blocker.html")

@app.route("/api/settings", methods=["GET"])
def get_s():
    if not os.path.exists(DB_FILE): return jsonify({})
    with open(DB_FILE, "r", encoding='utf-8') as f: s = json.load(f)
    
    now = time.time()
    to_move = []
    
    # 시간이 다 된 사이트 찾기
    for name, group_data in s.get("active_groups", {}).items():
        if isinstance(group_data, dict):
            if now > group_data.get("end_time", 0):
                to_move.append(name)
        else:
            to_move.append(name)
            
    # 시간이 다 된 애들을 영구 삭제하지 않고 '차단 후보'로 복구
    for name in to_move:
        if isinstance(s["active_groups"][name], dict):
            s["candidate_groups"][name] = s["active_groups"].pop(name)["keywords"]
        else:
            s["candidate_groups"][name] = s["active_groups"].pop(name)
            
    if to_move:
        with open(DB_FILE, "w", encoding='utf-8') as f: json.dump(s, f, ensure_ascii=False, indent=2)
        
    return jsonify(s)

@app.route("/api/settings", methods=["POST"])
def update_s():
    data = request.json
    if not os.path.exists(DB_FILE):
        s = {"candidate_groups": {}, "active_groups": {}, "blanket_text": "공부합시다!", "emergency_sentences": []}
    else:
        with open(DB_FILE, "r", encoding='utf-8') as f: s = json.load(f)
    
    if "groups" in s: s["candidate_groups"] = s.pop("groups")
    if "candidate_groups" not in s: s["candidate_groups"] = {}
    if "active_groups" not in s: s["active_groups"] = {}

    if "url" in data and data["url"]:
        original_url = data["url"].strip()
        u = original_url.lower()
        clean = u.replace("https://", "").replace("http://", "").replace("www.", "")
        if "/" in clean: clean = clean.split("/")[0]
        brand = clean.split(".")[0]
        
        primary_label = brand
        related_keywords = [clean, brand]
        
        if brand in INFERENCE_MAP:
            primary_label = INFERENCE_MAP[brand][0]
            related_keywords.extend(INFERENCE_MAP[brand])
        else:
            fetched_title = get_website_title(original_url)
            if fetched_title:
                primary_label = fetched_title
                related_keywords.append(fetched_title)
        
        s["candidate_groups"][primary_label] = list(set(related_keywords))

    if "duration" in data and "targets" in data:
        duration_sec = float(data["duration"]) * 3600
        targets = data.get("targets", [])
        for t in targets:
            if t in s["candidate_groups"]:
                s["active_groups"][t] = {
                    "keywords": s["candidate_groups"].pop(t),
                    "end_time": time.time() + duration_sec
                }

    if "blanket_text" in data: s["blanket_text"] = data["blanket_text"]
    if "emergency_sentences" in data: s["emergency_sentences"] = data["emergency_sentences"]
    
    with open(DB_FILE, "w", encoding='utf-8') as f: json.dump(s, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})

@app.route("/api/unlock", methods=["POST"])
def unlock():
    req_data = request.json or {}
    targets = req_data.get("targets", [])
    
    with open(DB_FILE, "r", encoding='utf-8') as f: s = json.load(f)
    if "candidate_groups" not in s: s["candidate_groups"] = {}
    if "active_groups" not in s: s["active_groups"] = {}

    # 긴급 해제 시 영구 삭제 안 하고 '차단 후보'로 복구
    if targets:
        for t in targets:
            if t in s["active_groups"]:
                group_data = s["active_groups"].pop(t)
                s["candidate_groups"][t] = group_data["keywords"] if isinstance(group_data, dict) else group_data

    with open(DB_FILE, "w", encoding='utf-8') as f: json.dump(s, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})

@app.route("/api/delete_site", methods=["POST"])
def delete_site():
    data = request.json or {}
    target = data.get("target")
    with open(DB_FILE, "r", encoding='utf-8') as f: s = json.load(f)
    
    if target:
        if target in s.get("candidate_groups", {}):
            del s["candidate_groups"][target]
        # 차단 중(active_groups)인 사이트는 여기서 지우지 않음!
            
    with open(DB_FILE, "w", encoding='utf-8') as f: json.dump(s, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)