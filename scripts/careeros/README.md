# Career OS 확인 도구

배포본이나 로컬 서버를 **읽어서 상태를 보여주는** 작은 스크립트들.
화면으로는 한눈에 안 들어오는 것(밀려서 빠진 일 · 마감이 지난 단계 · 이름이 겹치는 프로젝트)을
한 화면에 모아 본다.

## 쓰는 법

```bash
cd scripts/careeros

python3 check_today_plan.py          # 오늘 계획 · 밀려서 빠진 것 · 마감 지난 단계
python3 check_path.py Tave           # 경로의 단계 · 마감 · 체크 진행
python3 check_path.py Tave --items   #   체크 항목까지 (단계를 쪼갤 때)
python3 check_projects.py            # 프로젝트 · 학습 경로 · 이름 겹침
python3 check_opportunities.py       # 공고 · 목표 직무 · 스킬 레벨
python3 export_production.py         # 데이터 통째로 백업 → ~/Documents/career-os/backups/
python3 rebuild_today_plan.py --apply  # 계획 다시 세우기 (전후 비교)

python3 set_due.py Tave 2주차 2026-10-06 --apply   # 단계 마감 바꾸기
python3 set_due.py Tave 1주차 none --apply         #   마감 없애기 (놓아두기)
```

## 일주일에 한 번 — 쌓인 공고 치우기

```bash
python3 tidy_postings.py          # 무엇을 치울지 보여주기만
python3 tidy_postings.py --apply  # 실제로
```

수집원이 다섯이라 같은 공고가 여러 번 들어온다. 한 회사가 요구하는 스킬이
네 배로 세어지면 수요 비율이 통째로 틀어진다. 중복은 보관함, 마감 지난 것은
닫음으로 **상태만** 바꾼다 — 지우지 않으니 화면에서 되돌릴 수 있다.

**지원서가 걸린 공고는 안 건드린다.** 치우면 그 지원서가 어느 공고인지
화면에서 사라진다 (2026-10-06 에 손으로 치우다 실제로 깨뜨렸다).

**원문을 다시 받아오지 않는다.** 공고 대부분이 url 이 비어 있고, 되는 것도
사이트마다 마감 표시가 달라 규칙으로 못 읽는다. 저장된 마감일로만 판단한다.

한글 음차는 못 묶는다 — "에스케이인텔릭스" 와 "SK인텔릭스" 는 다른 회사로
본다. 사전이 필요한 일이고, 틀리게 묶는 쪽이 더 나쁘다.

## 로컬로 옮기기 (Railway Trial 만료 대비 — `docs/LOCAL.md`)

```bash
python3 export_production.py                       # 배포본 → backups/*.json
python3 import_local.py ../../backups/<파일>.json   # 파일 → 이 노트북
bash ../local.sh                                   # http://localhost:8000
```

`import_local.py` 는 **서버를 안 거친다.** SQLite 파일을 직접 열어서
비밀번호가 필요 없고, 배포본은 건드리지 않는다. 기존 로컬 데이터는
전부 지워지므로 무엇이 사라지는지 보여주고 한 번 물어본다.

`rebuild_today_plan.py` 와 `set_due.py` 만 서버를 바꾼다. 나머지는 **읽기 전용**이고,
바꾸는 둘도 `--apply` 가 없으면 전후만 보여준다.

## 어디를 보는가

| | |
|---|---|
| 기본 | 배포본. 아이디를 묻고, 비밀번호는 `getpass` 로 받는다 |
| 로컬 | `BASE=http://localhost:8130 python3 …` — 인증을 안 묻는다 |
| 아이디 고정 | `export CAREER_USER=...` 해두면 매번 안 묻는다 |

**아이디 · 비밀번호는 이 저장소에 없다.** 매번 입력하거나 환경변수로 준다.

## 왜 여기 있나

원래 `~/Downloads/` 아래에 흩어져 있었다. git 밖이라 고쳐도 기록이 안 남고,
어느 것이 최신인지 알 수 없었다. 계속 쓸 것만 여기로 옮겼다 (2026-09-28).

한 번 쓰고 버리는 스크립트(어떤 경로의 마감을 옮기는 등)는 여기 두지 않는다.
그건 그때그때 만들고 지운다 — 무엇을 왜 했는지는 `notes/sessions/` 에 남는다.
