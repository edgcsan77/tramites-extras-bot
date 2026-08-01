from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuthorizedGroup,
    BotControl,
    CfeRequest,
    RenapoRequest,
)


PANEL_TZ = ZoneInfo("America/Monterrey")

PENDING_STATUSES = {
    "QUEUED",
    "PROCESSING",
    "WAITING_PROVIDER",
}


def to_panel_tz(value):
    if not value:
        return None

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        PANEL_TZ
    )


def fmt_dt(value) -> str:
    value = to_panel_tz(value)

    if not value:
        return ""

    return value.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def period_bounds(
    view: str,
    date_from: str = "",
    date_to: str = "",
):
    now = datetime.now(PANEL_TZ)
    view = (
        view
        or "day"
    ).strip().lower()

    if view == "custom" and date_from:
        start = datetime.strptime(
            date_from,
            "%Y-%m-%d",
        ).replace(
            tzinfo=PANEL_TZ
        )

        end = datetime.strptime(
            date_to or date_from,
            "%Y-%m-%d",
        ).replace(
            tzinfo=PANEL_TZ
        ) + timedelta(days=1)

    elif view == "30d":
        start = (
            now
            - timedelta(days=29)
        ).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        end = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ) + timedelta(days=1)

    elif view == "month":
        start = now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        if start.month == 12:
            end = start.replace(
                year=start.year + 1,
                month=1,
            )
        else:
            end = start.replace(
                month=start.month + 1,
            )

    elif view == "prev_month":
        end = now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        previous = (
            end
            - timedelta(days=1)
        )

        start = previous.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    else:
        view = "day"

        start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        end = (
            start
            + timedelta(days=1)
        )

    return (
        start.astimezone(timezone.utc),
        end.astimezone(timezone.utc),
        view,
    )


def _load_requests(
    db: Session,
    time_min,
    time_max,
    *,
    instance_name: str = "",
    group_jid: str = "",
):
    cfe_query = select(
        CfeRequest
    ).where(
        CfeRequest.created_at >= time_min,
        CfeRequest.created_at < time_max,
    )

    renapo_query = select(
        RenapoRequest
    ).where(
        RenapoRequest.created_at >= time_min,
        RenapoRequest.created_at < time_max,
    )

    if instance_name:
        cfe_query = cfe_query.where(
            CfeRequest.client_instance
            == instance_name
        )

        renapo_query = renapo_query.where(
            RenapoRequest.client_instance
            == instance_name
        )

    if group_jid:
        cfe_query = cfe_query.where(
            CfeRequest.client_group_jid
            == group_jid
        )

        renapo_query = renapo_query.where(
            RenapoRequest.client_group_jid
            == group_jid
        )

    cfe_rows = list(
        db.scalars(
            cfe_query.order_by(
                CfeRequest.created_at.desc()
            )
        ).all()
    )

    renapo_rows = list(
        db.scalars(
            renapo_query.order_by(
                RenapoRequest.created_at.desc()
            )
        ).all()
    )

    return cfe_rows, renapo_rows


def summary_from_rows(
    cfe_rows,
    renapo_rows,
):
    statuses = Counter(
        [row.status for row in cfe_rows]
        + [row.status for row in renapo_rows]
    )

    return {
        "total":
            len(cfe_rows)
            + len(renapo_rows),

        "done":
            statuses.get("DONE", 0),

        "pending":
            sum(
                statuses.get(status, 0)
                for status in PENDING_STATUSES
            ),

        "no_record":
            statuses.get("NO_RECORD", 0),

        "errors":
            statuses.get("ERROR", 0),

        "disabled":
            statuses.get("DISABLED", 0),

        "cfe_total":
            len(cfe_rows),

        "renapo_total":
            len(renapo_rows),

        "cfe_done":
            sum(
                1
                for row in cfe_rows
                if row.status == "DONE"
            ),

        "renapo_done":
            sum(
                1
                for row in renapo_rows
                if row.status == "DONE"
            ),
    }


def group_rows(
    db: Session,
    cfe_rows,
    renapo_rows,
):
    requests_by_group = defaultdict(
        lambda: {
            "total": 0,
            "done": 0,
            "pending": 0,
            "errors": 0,
            "no_record": 0,
            "cfe": 0,
            "renapo": 0,
            "last_update": None,
        }
    )

    for product, rows in (
        ("CFE", cfe_rows),
        ("RENAPO", renapo_rows),
    ):
        for row in rows:
            group_jid = (
                row.client_group_jid
                or ""
            ).strip()

            if not group_jid:
                continue

            item = requests_by_group[
                group_jid
            ]

            item["total"] += 1
            item[
                product.lower()
            ] += 1

            if row.status == "DONE":
                item["done"] += 1

            elif row.status in PENDING_STATUSES:
                item["pending"] += 1

            elif row.status == "ERROR":
                item["errors"] += 1

            elif row.status == "NO_RECORD":
                item["no_record"] += 1

            updated = (
                getattr(
                    row,
                    "completed_at",
                    None,
                )
                or getattr(
                    row,
                    "updated_at",
                    None,
                )
                or row.created_at
            )

            if (
                not item["last_update"]
                or updated
                > item["last_update"]
            ):
                item[
                    "last_update"
                ] = updated

    group_ids = list(
        requests_by_group
    )

    configured_rows = []

    if group_ids:
        configured_rows = list(
            db.scalars(
                select(
                    AuthorizedGroup
                ).where(
                    AuthorizedGroup.group_jid
                    .in_(group_ids)
                )
            ).all()
        )

    configured = {
        row.group_jid: row
        for row in configured_rows
    }

    result = []

    for group_jid, stats in (
        requests_by_group.items()
    ):
        row = configured.get(
            group_jid
        )

        result.append({
            "group_jid":
                group_jid,

            "group_name":
                (
                    row.custom_name
                    if row
                    and row.custom_name
                    else group_jid
                ),

            "owner_instance":
                (
                    row.owner_instance
                    if row
                    else ""
                ),

            "category":
                (
                    row.category
                    if row
                    else ""
                ),

            "blocked":
                bool(
                    row.is_blocked
                )
                if row
                else False,

            "hidden":
                bool(
                    row.hidden_in_main
                )
                if row
                else False,

            "price_cfe":
                row.price_cfe
                if row
                else None,

            "price_renapo":
                row.price_renapo
                if row
                else None,

            "cfe_limit":
                int(
                    row.cfe_limit or 0
                )
                if row
                else 0,

            "cfe_used":
                int(
                    row.cfe_used or 0
                )
                if row
                else 0,

            "renapo_limit":
                int(
                    row.renapo_limit or 0
                )
                if row
                else 0,

            "renapo_used":
                int(
                    row.renapo_used or 0
                )
                if row
                else 0,

            **stats,
        })

    result = [
        row
        for row in result
        if not row["hidden"]
    ]

    result.sort(
        key=lambda row: (
            -row["done"],
            row["group_name"].lower(),
        )
    )

    return result


def recent_rows(
    db: Session,
    cfe_rows,
    renapo_rows,
    limit: int = 30,
):
    rows = []

    group_jids = {
        str(
            row.client_group_jid
            or ""
        ).strip()
        for row in (
            list(cfe_rows)
            + list(renapo_rows)
        )
        if str(
            row.client_group_jid
            or ""
        ).strip()
    }

    configured_groups = []

    if group_jids:
        configured_groups = list(
            db.scalars(
                select(
                    AuthorizedGroup
                ).where(
                    AuthorizedGroup.group_jid
                    .in_(group_jids)
                )
            ).all()
        )

    group_names = {
        str(
            group.group_jid
            or ""
        ).strip(): (
            str(
                group.custom_name
                or ""
            ).strip()
            or str(
                group.group_jid
                or ""
            ).strip()
        )
        for group in configured_groups
    }

    for row in cfe_rows:
        group_jid = str(
            row.client_group_jid
            or ""
        ).strip()

        rows.append({
            "created_at":
                row.created_at,

            "module":
                "CFE",

            "id":
                row.id,

            "identifier":
                row.service_number,

            "status":
                row.status,

            "group_jid":
                group_jid,

            "group_name":
                group_names.get(
                    group_jid,
                    group_jid,
                ),

            "instance":
                row.client_instance,

            "requester":
                row.requester_name or "",

            "error":
                row.error_message or "",
        })

    for row in renapo_rows:
        group_jid = str(
            row.client_group_jid
            or ""
        ).strip()

        rows.append({
            "created_at":
                row.created_at,

            "module":
                "RENAPO",

            "id":
                row.id,

            "identifier":
                row.curp,

            "status":
                row.status,

            "group_jid":
                group_jid,

            "group_name":
                group_names.get(
                    group_jid,
                    group_jid,
                ),

            "instance":
                row.client_instance,

            "requester":
                "",

            "error":
                row.error_message or "",
        })

    rows.sort(
        key=lambda item:
            item["created_at"]
            or datetime.min.replace(
                tzinfo=timezone.utc
            ),
        reverse=True,
    )

    return rows[:limit]


def main_panel_data(
    db: Session,
    time_min,
    time_max,
):
    cfe_rows, renapo_rows = (
        _load_requests(
            db,
            time_min,
            time_max,
        )
    )

    return {
        "summary":
            summary_from_rows(
                cfe_rows,
                renapo_rows,
            ),

        "groups":
            group_rows(
                db,
                cfe_rows,
                renapo_rows,
            ),

        "recent":
            recent_rows(
                db,
                cfe_rows,
                renapo_rows,
            ),
    }


def bot_panel_data(
    db: Session,
    instance_name: str,
    time_min,
    time_max,
):
    cfe_rows, renapo_rows = (
        _load_requests(
            db,
            time_min,
            time_max,
            instance_name=instance_name,
        )
    )

    groups = list(
        db.scalars(
            select(
                AuthorizedGroup
            ).where(
                AuthorizedGroup.owner_instance
                == instance_name,

                AuthorizedGroup.is_hidden
                .is_(False),
            ).order_by(
                AuthorizedGroup.created_at.desc()
            )
        ).all()
    )

    return {
        "summary":
            summary_from_rows(
                cfe_rows,
                renapo_rows,
            ),

        "groups":
            groups,

        "recent":
            recent_rows(
                db,
                cfe_rows,
                renapo_rows,
                limit=40,
            ),
    }
