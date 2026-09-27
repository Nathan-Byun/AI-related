# 뜯어보는 사람들 아카이브

제품·기기·설비를 분해하고 설계를 거꾸로 읽어 내는 유튜브 채널과 웹사이트 251곳을 모은 웹앱입니다.
GitHub에 올려 두면 매일 새벽 채널별 새 영상이 자동으로 채워지고, 매달 1일에 링크가 살아 있는지 자동으로 점검합니다.

## 무엇이 자동으로 도는가

| 작업 | 시점 | 하는 일 |
|---|---|---|
| 새 콘텐츠 갱신 | 매일 한국 시간 06:00 | 유튜브 채널 162곳의 새 영상과 웹사이트 89곳의 새 글을 읽어 최근 30일치 제목·날짜·요약을 모읍니다 |
| 링크 점검 | 매달 1일 한국 시간 09:00 | 251곳 주소에 접속해 응답을 확인하고, 끊긴 곳과 옮겨 간 곳을 표시합니다 |

결과는 `data/uploads.json`, `data/checks.json`에 저장되고 웹앱이 그 파일을 읽습니다.
컴퓨터를 켜 둘 필요도, 로그인할 필요도 없습니다.

## 설치 (한 번만)

1. **저장소 만들기** — GitHub에서 New repository를 누르고 이름을 정합니다(예: `teardown-archive`). Public으로 두세요. Private은 GitHub Pages가 유료 플랜에서만 됩니다.
2. **파일 올리기** — 저장소 화면에서 `Add file` → `Upload files`를 누르고, 이 폴더의 내용물을 통째로 끌어다 놓습니다(`index.html`, `data`, `scripts`, `.github`, `.nojekyll`). 아래 `Commit changes`를 누릅니다.
3. **쓰기 권한 켜기** — `Settings` → `Actions` → `General` → 아래쪽 `Workflow permissions`에서 **Read and write permissions**를 고르고 저장합니다. 이걸 해야 수집 결과가 저장됩니다.
4. **주소 만들기** — `Settings` → `Pages` → Source를 `Deploy from a branch`, Branch를 `main` / `/ (root)`로 두고 저장합니다. 1~2분 뒤 `https://<아이디>.github.io/<저장소이름>/` 으로 열립니다.
5. **첫 수집 돌리기** — `Actions` 탭 → 왼쪽에서 `새 콘텐츠 갱신` → 오른쪽 `Run workflow`. 첫 회는 채널 ID를 찾느라 10~20분쯤 걸립니다. 다음부터는 몇 분이면 끝납니다.

이제 4번에서 나온 주소를 북마크하거나 휴대폰 홈 화면에 추가하면 됩니다.

## 한국어 요약 (선택)

영상 설명은 채널 언어 그대로라 대부분 영어입니다. 한국어 한 줄 요약을 붙이고 싶으면:

1. Anthropic 콘솔에서 API 키를 발급합니다.
2. 저장소 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`.
3. 이름은 `ANTHROPIC_API_KEY`, 값은 발급한 키.

키가 있으면 수집 후 자동으로 한국어 요약이 붙고, 없으면 그 단계만 건너뜁니다. 원문 설명은 `s0`에 남습니다.

## 직접 돌려 보기

```bash
python scripts/update.py ids      # 채널 ID 찾기 (없는 것만)
python scripts/update.py uploads  # 유튜브 새 영상 모으기
python scripts/update.py sites    # 웹사이트 새 글 모으기
python scripts/update.py check    # 링크 점검
python -m http.server 8000        # 브라우저에서 localhost:8000 열기
```

표준 라이브러리만 씁니다. 설치할 패키지가 없습니다.

## 폴더 구성

```
index.html                   웹앱 한 파일
data/channels.json           채널·사이트 251곳의 목록과 설명 (사람이 관리)
data/channel_ids.json        유튜브 채널 ID 캐시 (자동)
data/site_feeds.json         웹사이트 RSS 주소 캐시 (자동)
data/uploads.json            최근 영상과 글 (자동, 매일)
data/checks.json             링크 점검 결과 (자동, 매달 1일)
scripts/update.py            수집·점검 스크립트
scripts/summarize.py         한국어 요약 (키가 있을 때만)
.github/workflows/           자동 실행 설정
```

## 알아 둘 점

- Public 저장소면 목록과 수집 결과를 누구나 볼 수 있습니다. 개인 메모는 넣지 마세요.
- '봤음'과 '확인함' 표시는 열어 본 기기의 브라우저에 저장됩니다. 컴퓨터와 휴대폰의 표시는 따로 남습니다.
- 채널 ID를 검색으로 찾은 경우 동명이인 채널이 걸릴 수 있습니다. `data/channel_ids.json`의 `found` 값이 채널 이름과 다르면 `cid`를 직접 고치세요.
- 채널이나 사이트를 더하거나 빼려면 `data/channels.json`을 고치면 됩니다.
