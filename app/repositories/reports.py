"""Monthly reports.

Report types are described by data (``REPORT_TYPES``); the routes, templates and logic are
shared by all of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from app import db, sql


@dataclass(frozen=True)
class ReportType:
    slug: str  # used in URLs
    title: str
    value_header: str  # caption of the value column
    create_sql: str  # CALL of the procedure that generates the report for a month
    rows_sql: str  # the rows of a generated report (account_num, value)
    periods_sql: str  # the months for which a report exists


REPORT_TYPES: dict[str, ReportType] = {
    rt.slug: rt
    for rt in (
        ReportType(
            slug="sent-sum",
            title="Отчёт о сумме переводов со счетов",
            value_header="Отправленная за месяц сумма",
            create_sql="reports/sent_sum_create.sql",
            rows_sql="reports/sent_sum_rows.sql",
            periods_sql="reports/sent_sum_periods.sql",
        ),
        ReportType(
            slug="transfer-count",
            title="Отчёт о количестве переводов за месяц",
            value_header="Количество переводов за месяц",
            create_sql="reports/transfer_count_create.sql",
            rows_sql="reports/transfer_count_rows.sql",
            periods_sql="reports/transfer_count_periods.sql",
        ),
    )
}


class CreateResult(Enum):
    ALREADY_EXISTS = "already_exists"
    CREATED = "created"
    NO_DATA = "no_data"


def list_periods(report: ReportType) -> list[date]:
    return [row["report_date"] for row in db.fetch_all(sql.load(report.periods_sql))]


def get_rows(report: ReportType, period: date) -> list[dict]:
    return db.fetch_all(sql.load(report.rows_sql), {"period": period.isoformat()})


def create(report: ReportType, period: date) -> CreateResult:
    if get_rows(report, period):
        return CreateResult.ALREADY_EXISTS
    # The procedure runs inside a single transaction: a report is stored completely or not at all.
    db.execute(sql.load(report.create_sql), {"period": period.isoformat()})
    return CreateResult.CREATED if get_rows(report, period) else CreateResult.NO_DATA
