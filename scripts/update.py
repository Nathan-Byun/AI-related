#!/usr/bin/env python3
"""뜯어보는 사람들 아카이브 갱신 스크립트.

사용법:
  python scripts/update.py ids      채널 ID를 찾아 data/channel_ids.json에 저장 (없는 것만)
  python scripts/update.py uploads  유튜브 채널의 최근 영상을 모아 data/uploads.json에 넣기
  python scripts/update.py sites    웹사이트의 최근 글을 모아 data/uploads.json에 넣기
  python scripts/update.py check    모든 주소에 접속해 data/checks.json 생성

표준 라이브러리만 씁니다. 설치할 것이 없습니다.
"""

import concurrent.futures as futures
import datetime as dt
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
DAYS = 183          # 새 콘텐츠로 볼 기간 (약 6개월)
MAX_ITEMS = 25      # 채널당 최대 보관 개수
SUM_LEN = 140       # 영상 설명에서 가져올 길이

NS = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/"}


def today():
    return dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=9))).date()


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.geturl(), r.read()


def load(name, default):
    p = DATA / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default
    return default


def save(name, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: data/{name}")


def channels():
    return load("channels.json", {}).get("channels", [])


# ---------------------------------------------------------------- 채널 ID

CID_RE = re.compile(r'"(?:channelId|externalId)":"(UC[\w-]{22})"')
CHANNEL_BLOCK_RE = re.compile(
    r'"channelRenderer":\{"channelId":"(UC[\w-]{22})".*?"title":\{"simpleText":"(.*?)"', re.S
)


def cid_from_url(url):
    m = re.search(r"/channel/(UC[\w-]{22})", url)
    if m:
        return m.group(1), "url"
    try:
        _, _, body = get(url)
    except Exception as e:
        print(f"  채널 페이지 실패: {url} ({e})")
        return None, None
    m = CID_RE.search(body.decode("utf-8", "ignore"))
    return (m.group(1), "page") if m else (None, None)


def cid_from_search(query):
    url = "https://www.youtube.com/results?" + urllib.parse.urlencode(
        {"search_query": query, "sp": "EgIQAg%3D%3D"}  # 채널만 보기
    )
    try:
        _, _, body = get(url)
    except Exception as e:
        print(f"  검색 실패: {query} ({e})")
        return None, None, None
    text = body.decode("utf-8", "ignore")
    m = CHANNEL_BLOCK_RE.search(text)
    if m:
        return m.group(1), "search", m.group(2)
    m = CID_RE.search(text)
    return (m.group(1), "search", None) if m else (None, None, None)


def cmd_ids(force=False):
    ids = load("channel_ids.json", {})
    todo = [c for c in channels() if c.get("kind", "yt") == "yt" and (force or c["id"] not in ids)]
    print(f"채널 ID 찾기: {len(todo)}곳")
    for c in todo:
        url = c.get("u")
        cid = src = title = None
        if url and "youtube.com" in url:
            cid, src = cid_from_url(url)
        if not cid:
            cid, src, title = cid_from_search(c.get("q") or c["n"])
        if cid:
            ids[c["id"]] = {"cid": cid, "src": src, "name": c["n"], "found": title, "at": str(today())}
            print(f"  {c['n']} -> {cid} ({src}) {title or ''}")
        else:
            print(f"  못 찾음: {c['n']}")
        time.sleep(1.0)  # 유튜브에 부담 주지 않도록
    save("channel_ids.json", ids)
    missing = [c["n"] for c in channels() if c.get("kind", "yt") == "yt" and c["id"] not in ids]
    if missing:
        print("아직 못 찾은 채널:", ", ".join(missing))


# ---------------------------------------------------------------- 영상 목록


def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > SUM_LEN:
        cut = text[:SUM_LEN].rsplit(" ", 1)[0]
        text = cut + "…"
    return text


def feed_items(cid, cutoff):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    _, _, body = get(url)
    root = ET.fromstring(body)
    out = []
    for e in root.findall("a:entry", NS):
        published = (e.findtext("a:published", default="", namespaces=NS) or "")[:10]
        if not published or published < cutoff:
            continue
        vid = e.findtext("a:id", default="", namespaces=NS).split(":")[-1]
        title = (e.findtext("a:title", default="", namespaces=NS) or "").strip()
        link = e.find("a:link", NS)
        href = link.get("href") if link is not None else f"https://www.youtube.com/watch?v={vid}"
        desc = e.findtext("m:group/m:description", default="", namespaces=NS)
        out.append({"k": vid, "t": title, "u": href, "d": published, "s": clean(desc)})
    out.sort(key=lambda x: x["d"], reverse=True)
    return out[:MAX_ITEMS]


def cmd_uploads():
    ids = load("channel_ids.json", {})
    if not ids:
        print("채널 ID가 없습니다. 먼저 `python scripts/update.py ids`를 실행하세요.")
        return
    cutoff = str(today() - dt.timedelta(days=DAYS))
    out, ok, fail = {}, 0, 0
    for c in channels():
        if c.get("kind", "yt") != "yt" or c["id"] not in ids:
            continue
        cid = ids[c["id"]]["cid"]
        try:
            items = feed_items(cid, cutoff)
            out[c["id"]] = {"items": items, "checkedAt": str(today())}
            ok += 1
            if items:
                print(f"  {c['n']}: {len(items)}개")
        except Exception as e:
            fail += 1
            print(f"  실패 {c['n']}: {e}")
        time.sleep(0.4)
    merge_uploads(out)
    print(f"완료: {ok}곳 수집, {fail}곳 실패")


def merge_uploads(new):
    doc = load("uploads.json", {})
    chans = doc.get("channels", {})
    chans.update(new)
    doc["channels"] = chans
    doc["updatedAt"] = str(today())
    doc["note"] = "요약은 각 채널·사이트가 쓴 설명 앞부분이라 원문 언어 그대로 나옵니다."
    save("uploads.json", doc)


# ---------------------------------------------------------------- 웹사이트 글

FEED_PATHS = ["/feed/", "/rss/", "/feed", "/index.xml", "/atom.xml", "/rss.xml",
              "/feeds/posts/default?alt=rss", "/blog/feed/"]
FEED_SIG = re.compile(rb"<(rss|feed|rdf:RDF)[\s>]", re.I)


def strip_ns(tag):
    return tag.split("}")[-1]


def parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw).date().isoformat()
    except Exception:
        pass
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return raw[:10] if re.match(r"\d{4}-\d{2}-\d{2}", raw) else ""


def discover_feed(url):
    try:
        _, final, body = get(url)
    except Exception as e:
        print(f"  홈페이지 실패: {url} ({e})")
        return None
    text = body.decode("utf-8", "ignore")
    for tag in re.findall(r"<link[^>]+>", text, re.I):
        if "alternate" in tag.lower() and re.search(r'type=["\'][^"\']*(rss|atom)', tag, re.I):
            href = re.search(r'href=["\']([^"\']+)', tag, re.I)
            if href:
                return urllib.parse.urljoin(final, href.group(1))
    for path in FEED_PATHS:
        cand = urllib.parse.urljoin(final, path)
        try:
            _, _, probe = get(cand, timeout=15)
        except Exception:
            continue
        if FEED_SIG.search(probe[:3000]):
            return cand
    return None


def feed_articles(feed_url, cutoff, limit=15):
    _, _, body = get(feed_url)
    root = ET.fromstring(body)
    out = []
    for node in root.iter():
        if strip_ns(node.tag) not in ("item", "entry"):
            continue
        fields = {}
        link = ""
        for child in node:
            name = strip_ns(child.tag)
            if name == "link":
                link = child.get("href") or (child.text or "").strip() or link
            else:
                fields.setdefault(name, (child.text or "").strip())
        published = parse_date(fields.get("pubDate") or fields.get("published")
                               or fields.get("date") or fields.get("updated"))
        if not published or published < cutoff:
            continue
        title = clean(re.sub(r"<[^>]+>", " ", fields.get("title", "")))
        body_text = fields.get("description") or fields.get("summary") or fields.get("encoded") or ""
        out.append({
            "k": fields.get("guid") or fields.get("id") or link,
            "t": title[:110],
            "u": link,
            "d": published,
            "s": clean(re.sub(r"<[^>]+>", " ", body_text)),
        })
    out.sort(key=lambda x: x["d"], reverse=True)
    return [x for x in out if x["u"].startswith("http")][:limit]


def cmd_sites():
    feeds = load("site_feeds.json", {})
    cutoff = str(today() - dt.timedelta(days=DAYS))
    out, ok, nofeed = {}, 0, []
    for c in channels():
        if c.get("kind") != "web" or not c.get("u"):
            continue
        url = feeds.get(c["id"])
        if url is None:
            url = discover_feed(c["u"])
            feeds[c["id"]] = url or ""
            time.sleep(0.5)
        if not url:
            nofeed.append(c["n"])
            continue
        try:
            items = feed_articles(url, cutoff)
            out[c["id"]] = {"items": items, "checkedAt": str(today())}
            ok += 1
            if items:
                print(f"  {c['n']}: {len(items)}개")
        except Exception as e:
            print(f"  실패 {c['n']}: {e}")
        time.sleep(0.4)
    save("site_feeds.json", feeds)
    merge_uploads(out)
    print(f"완료: {ok}곳 수집, 피드 없는 곳 {len(nofeed)}곳")
    if nofeed:
        print("  피드 없음:", ", ".join(nofeed[:20]))


# ---------------------------------------------------------------- 링크 점검


def check_one(c, ids):
    url = c.get("u")
    if not url:
        cid = ids.get(c["id"], {}).get("cid")
        if not cid:
            return c["id"], {"st": "skip"}
        url = f"https://www.youtube.com/channel/{cid}"
    try:
        status, final, _ = get(url, timeout=20)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return c["id"], {"st": "dead", "at": str(today()), "n": f"{e.code} 응답"}
        if e.code in (401, 403, 429):
            return c["id"], {"st": "ok", "at": str(today()), "n": f"{e.code}(자동 접속 차단)"}
        return c["id"], {"st": "warn", "at": str(today()), "n": f"{e.code} 응답"}
    except Exception as e:
        return c["id"], {"st": "warn", "at": str(today()), "n": f"접속 실패: {type(e).__name__}"}
    host_before = urllib.parse.urlsplit(url).netloc.lower().replace("www.", "")
    host_after = urllib.parse.urlsplit(final).netloc.lower().replace("www.", "")
    if host_before != host_after:
        return c["id"], {"st": "moved", "at": str(today()), "n": f"{host_after}로 이동"}
    return c["id"], {"st": "ok", "at": str(today())}


def cmd_check():
    ids = load("channel_ids.json", {})
    rows = channels()
    result = {}
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        for cid, res in pool.map(lambda c: check_one(c, ids), rows):
            result[cid] = res
    bad = {k: v for k, v in result.items() if v.get("st") not in ("ok", "skip")}
    counts = {}
    for v in result.values():
        counts[v.get("st", "?")] = counts.get(v.get("st", "?"), 0) + 1
    save(
        "checks.json",
        {
            "at": str(today()),
            "scope": f"전체 {len(rows)}곳 점검",
            "note": f"정상 {counts.get('ok', 0)}곳, 주소 바뀜 {counts.get('moved', 0)}곳, "
                    f"확인 필요 {counts.get('warn', 0)}곳, 링크 끊김 {counts.get('dead', 0)}곳.",
            "counts": counts,
            "items": bad,
        },
    )
    for k, v in bad.items():
        print(f"  {k}: {v['st']} {v.get('n', '')}")
    print(f"완료: 문제 {len(bad)}곳")


# ---------------------------------------------------------------- 진입점

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "ids":
        cmd_ids(force="--all" in sys.argv)
    elif cmd == "uploads":
        cmd_uploads()
    elif cmd == "sites":
        cmd_sites()
    elif cmd == "check":
        cmd_check()
    else:
        print(__doc__)
        sys.exit(1)
