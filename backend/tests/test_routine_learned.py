"""루틴 기록의 "몰랐던 것" — 그날 막힌 지점.

개수만 세면 "3문제 풀었다" 는 남지만 "왜 못 풀었는지" 는 안 남는다.
코테 전날 다시 볼 것은 푼 개수가 아니라 그때 막힌 지점이다.

2026-09-17 은 목요일이다.
"""

from datetime import date, datetime

from app import models
from app.services import routine as routine_service


THURSDAY = date(2026, 9, 17)


def _routine(db_session, title="코딩테스트", target=3, unit="문제"):
    routine = models.Routine(
        title=title, minutes=30, weekdays="0123456",
        target_count=target, unit_label=unit,
        created_at=datetime(2026, 9, 1, 9, 0),
    )
    db_session.add(routine)
    db_session.commit()
    return routine


def test_기록할_때_몰랐던_것을_함께_남긴다(db_session):
    routine = _routine(db_session)

    routine_service.record(db_session, routine, THURSDAY, 2, "투 포인터 while 조건을 언제 끊는지 몰랐다")
    db_session.commit()

    log = routine.logs[0]
    assert log.count == 2
    assert log.learned == "투 포인터 while 조건을 언제 끊는지 몰랐다"


def test_개수만_다시_고쳐도_적어_둔_것은_안_지워진다(db_session):
    """개수를 고치려고 다시 누를 때 그날 메모가 사라지면 안 된다."""
    routine = _routine(db_session)
    routine_service.record(db_session, routine, THURSDAY, 2, "해시로 세는 걸 못 떠올렸다")
    db_session.commit()

    routine_service.record(db_session, routine, THURSDAY, 3)  # learned 를 안 준다
    db_session.commit()

    log = routine.logs[0]
    assert log.count == 3
    assert log.learned == "해시로 세는 걸 못 떠올렸다"


def test_빈_문자열을_보내면_지운다(db_session):
    """지우는 것도 사람의 선택이다. 안 보내는 것(None)과 다르다."""
    routine = _routine(db_session)
    routine_service.record(db_session, routine, THURSDAY, 3, "적었다")
    db_session.commit()

    routine_service.record(db_session, routine, THURSDAY, 3, "")
    db_session.commit()

    assert routine.logs[0].learned == ""


def test_앞뒤_공백은_버린다(db_session):
    routine = _routine(db_session)
    routine_service.record(db_session, routine, THURSDAY, 1, "  DFS 재귀 깊이  \n")
    db_session.commit()

    assert routine.logs[0].learned == "DFS 재귀 깊이"


def test_모아보기는_적은_날만_최근부터_모은다(db_session):
    """안 적은 날까지 세면 목록이 기록이 아니라 달력이 된다."""
    routine = _routine(db_session)
    routine_service.record(db_session, routine, date(2026, 9, 15), 3, "이분 탐색 경계")
    routine_service.record(db_session, routine, date(2026, 9, 16), 3)          # 안 적은 날
    routine_service.record(db_session, routine, date(2026, 9, 17), 2, "위상 정렬")
    db_session.commit()

    entries = routine_service.learned_entries(db_session)

    assert [entry["learned"] for entry in entries] == ["위상 정렬", "이분 탐색 경계"]
    assert entries[0]["date"] == date(2026, 9, 17)
    assert entries[0]["routine_title"] == "코딩테스트"
    assert entries[0]["count"] == 2
    assert entries[0]["unit_label"] == "문제"


def test_모아보기를_루틴_하나로_좁힐_수_있다(db_session):
    kote = _routine(db_session, "코딩테스트")
    rehab = _routine(db_session, "coding rehab", target=None, unit="")

    routine_service.record(db_session, kote, THURSDAY, 3, "그리디 증명")
    routine_service.record(db_session, rehab, THURSDAY, None, "클래스와 인스턴스 구분")
    db_session.commit()

    only = routine_service.learned_entries(db_session, routine_id=rehab.id)

    assert [entry["learned"] for entry in only] == ["클래스와 인스턴스 구분"]


def test_화면에_주는_값에도_들어간다(db_session):
    """루틴 카드는 오늘 것과 최근 7일을 같이 보여 준다."""
    routine = _routine(db_session)
    routine_service.record(db_session, routine, THURSDAY, 3, "누적합")
    db_session.commit()

    data = routine_service.serialize(routine, THURSDAY)

    assert data["today_log"] == {"count": 3, "learned": "누적합"}
    assert data["recent"][-1]["learned"] == "누적합"
    assert data["recent"][0]["learned"] == ""      # 기록 없는 날


def test_메모만_고칠_때_개수가_목표로_올라가지_않는다(db_session):
    """2문제 푼 날에 메모만 덧붙였는데 3문제가 되면 기록이 사실과 달라진다."""
    routine = _routine(db_session, target=3)
    routine_service.record(db_session, routine, THURSDAY, 2)
    db_session.commit()

    routine_service.record(db_session, routine, THURSDAY, None, "스택으로 푸는 걸 몰랐다")
    db_session.commit()

    log = routine.logs[0]
    assert log.count == 2
    assert log.learned == "스택으로 푸는 걸 몰랐다"


def test_처음_남기는_날은_목표만큼_한_것으로_본다(db_session):
    """오늘 계획의 '완료' 는 개수를 안 줄 때가 있다. 그때는 종전대로 목표만큼."""
    routine = _routine(db_session, target=3)
    routine_service.record(db_session, routine, THURSDAY)
    db_session.commit()

    assert routine.logs[0].count == 3
