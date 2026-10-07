"""자동화 파이프라인.

Mission 023 부터 수집 대상은 Opportunity 다.
레거시 `Job` 은 대시보드와 기존 매칭이 아직 쓰고 있어서
`opportunity_service` 가 job 형태의 기회를 Job 으로도 이어준다.

파이프라인:

    수집원 실행 → Opportunity 저장 → 스킬 연결 → 레거시 Job 브릿지
        → 기회 채점 → 시장 스냅샷 → 상태 반환
"""

from .agents.tools import (
    get_learning_priority,
    get_active_projects,
    get_saved_resources,
    get_jobs,
)
from .services import market as market_service
from .services import tidy as tidy_service
from .services import opportunity as opportunity_service


def run_career_automation(db):
    collection = opportunity_service.collect_all(db)

    # 받자마자 치운다. 수집원이 다섯이라 같은 공고가 여러 줄로 들어오고,
    # 서울 밖 박람회도 매번 새로 들어온다. 사람이 tidy 를 돌리기 전까지
    # 그것들이 수요의 분모에 앉아 있고, 심하면 추천 자리까지 차지한다
    # (실제로 "부천 중장년 취업박람회" 가 맨 위 추천으로 떴다).
    #
    # 점수를 매기기 **전에** 한다 — 치울 것을 굳이 점수까지 내서 버릴
    # 이유가 없다.
    tidied = tidy_service.apply(db)

    matches = opportunity_service.score_all(db)

    snapshot_rows = market_service.capture_snapshot(db)

    learning_priority = get_learning_priority(db)
    projects = get_active_projects(db)
    resources = get_saved_resources(db)
    jobs = get_jobs(db)

    worth_doing = [
        match
        for match in matches
        if match["recommendation"] in ("recommended", "consider")
    ]

    return {
        # 받자마자 치운 것 — 중복 · 마감 · 서울 밖 행사.
        "tidied": {
            "archived": tidied["will_archive"],
            "closed": tidied["will_close"],
        },
        "status": "completed",

        # 기존 대시보드가 읽는 키. 형태를 유지한다.
        "collector": {
            "fetched_count": collection["fetched"],
            "created_count": collection["created"],
            "skipped_count": collection["updated"],
        },

        "opportunities": {
            "sources": collection["sources"],
            "fetched": collection["fetched"],
            "created": collection["created"],
            "updated": collection["updated"],
            "scored": len(matches),
            "worth_doing": len(worth_doing),
            "top": worth_doing[:3],
        },

        "market": {
            "snapshot_rows": snapshot_rows,
            "total_opportunities": market_service.count_opportunities(db),
        },

        "career_state": {
            "jobs_count": len(jobs),
            "projects_count": len(projects),
            "resources_count": len(resources),
            "learning_priority": learning_priority,
        },
    }
