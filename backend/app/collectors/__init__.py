"""수집원 레지스트리.

## 새 수집원을 추가하는 법

1. 이 디렉터리에 모듈을 하나 만든다 (`mock.py` 를 참고).
2. 아래 세 가지를 노출한다.

       SOURCE_NAME: str
       is_available() -> bool      자격 증명이 있는지 등
       fetch() -> list[dict]       원본 그대로
       normalize(raw) -> dict      base.normalize_opportunity() 사용

3. 아래 REGISTRY 에 등록한다.

## 지켜야 할 것

- **각 소스의 약관과 허용된 접근 방식을 먼저 확인한다.**
  모든 사이트를 스크래핑할 수 있다고 가정하지 않는다.
- 수집원은 데이터를 가져오고 형태만 맞춘다.
  점수 계산이나 추천 판단은 services/ 가 한다.
- 값을 추측해서 채우지 않는다. 없으면 비운다.
"""

from . import base, mock, saramin, work24, work24_events


REGISTRY = {
    mock.SOURCE_NAME: mock,
    saramin.SOURCE_NAME: saramin,
    work24.SOURCE_NAME: work24,
    work24_events.SOURCE_NAME: work24_events,
}


def get_collector(name: str):
    """이름으로 수집원을 찾는다. 없으면 None."""
    return REGISTRY.get(name)


def available_collectors() -> list:
    """지금 사용할 수 있는 수집원만 돌려준다."""
    return [
        collector
        for collector in REGISTRY.values()
        if collector.is_available()
    ]


__all__ = [
    "base",
    "REGISTRY",
    "get_collector",
    "available_collectors",
]
