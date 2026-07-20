"""Events — V12 §8.5. Mock: return sample timeline."""

from app.agents.state import (
    AgentState,
    ModuleStatus,
    EvidenceRef,
    EventsResult,
    ModuleResults,
)


def events_node(state: AgentState) -> dict:
    return {
        "module_status": {"events": ModuleStatus(state="success", duration_ms=90)},
        "results": ModuleResults(
            events=EventsResult(
                timeline=[
                    {
                        "date": "2018-10",
                        "title": "自媒体质疑财务数据",
                        "category": "舆情",
                    },
                    {
                        "date": "2018-12",
                        "title": "收到证监会立案调查",
                        "category": "监管",
                    },
                    {
                        "date": "2019-04",
                        "title": "会计差错更正,调减货币资金299亿",
                        "category": "公告",
                    },
                    {"date": "2019-05", "title": "实施ST", "category": "监管"},
                ],
                clusters=[
                    {
                        "topic": "财务造假风波",
                        "event_count": 4,
                        "date_range": "2018-10 至 2019-05",
                    },
                ],
                evidence=[
                    EvidenceRef(
                        evidence_id="ev_ev_01",
                        source_type="announcement",
                        source_record_id="ann_5507060000",
                        source_title="违纪违规公告",
                    )
                ],
            )
        ),
    }
