#!/usr/bin/env python3
"""영상 설명을 한국어 한 줄로 바꿔 줍니다 (선택 기능).

ANTHROPIC_API_KEY 가 있을 때만 동작합니다. 키가 없으면 그냥 건너뜁니다.
원래 설명은 s0 에 남겨 둡니다.
"""
import json, os, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
UP = ROOT / "data" / "uploads.json"
MODEL = "claude-haiku-4-5-20251001"
BATCH = 30

KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not KEY:
    print("ANTHROPIC_API_KEY 가 없어 한국어 요약을 건너뜁니다.")
    raise SystemExit(0)
if not UP.exists():
    print("uploads.json 이 없습니다.")
    raise SystemExit(0)

doc = json.loads(UP.read_text(encoding="utf-8"))
todo = []
for cid, ch in doc.get("channels", {}).items():
    for it in ch.get("items", []):
        if it.get("ko"):
            continue
        todo.append(it)
print(f"요약할 영상 {len(todo)}개")


def ask(items):
    lines = [{"i": n, "t": it.get("t", ""), "d": it.get("s", "")} for n, it in enumerate(items)]
    prompt = (
        "아래는 유튜브 영상의 제목과 설명이다. 각 영상이 무엇을 다루는지 한국어 한 문장으로 "
        "요약하라. 문장은 40자 안팎으로 짧게, 광고 문구와 구독 요청은 빼고 내용만 적는다. "
        "설명이 비어 있으면 제목만 보고 쓴다. 반드시 JSON 배열만 출력한다. "
        '형식: [{"i":0,"ko":"요약"}]\n\n' + json.dumps(lines, ensure_ascii=False)
    )
    body = json.dumps(
        {"model": MODEL, "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]}
    ).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    text = "".join(b.get("text", "") for b in out.get("content", []))
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


for start in range(0, len(todo), BATCH):
    chunk = todo[start : start + BATCH]
    try:
        for row in ask(chunk):
            n = row.get("i")
            if isinstance(n, int) and 0 <= n < len(chunk) and row.get("ko"):
                it = chunk[n]
                it["s0"] = it.get("s", "")
                it["s"] = row["ko"]
                it["ko"] = 1
    except Exception as e:
        print(f"  요약 실패: {e}")
        break

UP.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print("저장: data/uploads.json")
