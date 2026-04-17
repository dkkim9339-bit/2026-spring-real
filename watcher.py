import json, time, sys, os
import pygetwindow as gw
import tkinter as tk

DB_FILE = "settings.json"
# 🔥 본진 방어를 위한 화이트리스트 (여기에 적힌 창은 절대 차단 안 됨!)
WHITELIST = ["사이트 차단하기", "localhost", "127.0.0.1", "127.0.0.1:5000"]

def get_active_title():
    try:
        win = gw.getActiveWindow()
        return win.title if win else ""
    except:
        return ""

def load_settings():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

def main():
    root = tk.Tk()
    root.attributes('-fullscreen', True) # 전체 화면으로 덮기
    root.attributes('-topmost', True)    # 항상 최상단에 유지
    root.withdraw() # 처음엔 화면을 숨겨둠

    # 덮어쓸 문구 라벨 설정
    label = tk.Label(root, text="", font=("Pretendard", 50, "bold"), fg="white", bg="#1d1d1f")
    label.pack(expand=True, fill="both")

    print("감시기(Watcher) 실행 중... (종료하려면 터미널에서 Ctrl+C)")

    while True:
        time.sleep(1) # 1초마다 화면 감시
        settings = load_settings()
        active_groups = settings.get("active_groups", {})
        blanket_text = settings.get("blanket_text", "공부합시다!")

        now = time.time()
        is_blocked = False
        title = get_active_title()
        
        # 1. 화이트리스트(본진 방어) 먼저 체크
        if any(safe_word in title for safe_word in WHITELIST):
            root.withdraw()
            root.update()
            continue

        # 2. 현재 창이 차단 목록에 있는지 체크
        for site, data in active_groups.items():
            if isinstance(data, dict):
                if now < data.get("end_time", 0): # 시간이 아직 남았을 때만
                    keywords = data.get("keywords", [])
                    for kw in keywords:
                        if kw.lower() in title.lower():
                            is_blocked = True
                            break
            if is_blocked:
                break

        # 3. 차단 대상이면 화면을 덮고, 아니면 숨김
        if is_blocked:
            label.config(text=blanket_text)
            root.deiconify() # 숨겨둔 검은 화면 띄우기
            root.lift()      # 최상단으로 올리기
        else:
            root.withdraw()  # 차단 대상 아니면 화면 숨기기
            
        root.update()

if __name__ == "__main__":
    main()