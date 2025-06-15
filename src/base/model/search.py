import re
from typing import Any, Dict, Type, TypeVar, TYPE_CHECKING, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.inspection import inspect
from sqlalchemy.sql import or_, func
from sqlalchemy.sql.selectable import Select
from sqlalchemy.orm import aliased

from base.model.relation import apply_relations
from .filter import apply_filters

if TYPE_CHECKING:
    from . import BaseModel

T = TypeVar("T", bound="BaseModel")
_DELIM_RE = re.compile(r"__|\.")


# --------------------------------------------------------------------------- #
def _apply_keyword_search(
    query: Select,
    cls: Type["BaseModel"],
    keyword: Optional[str],
    search_fields: List[str],
) -> Select:
    if not keyword or not search_fields:
        return query

    aliases: Dict[str, Any] = {}
    conditions = []

    for field in search_fields:
        parts = _DELIM_RE.split(field)
        if len(parts) > 1:
            *rels, col = parts
            current = cls
            for rel in rels:
                if rel not in aliases:
                    Related = getattr(current, rel).property.mapper.class_
                    alias = aliased(Related)
                    query = query.join(alias, getattr(current, rel))
                    aliases[rel] = alias
                current = aliases[rel]
            column = getattr(current, col)
        else:
            column = getattr(cls, parts[0])

        conditions.append(column.ilike(f"%{keyword}%"))

    return query.where(or_(*conditions))


# --------------------------------------------------------------------------- #
async def _search(
    cls: Type[T],
    db: AsyncSession,
    keyword: Optional[str] = None,
    search_fields: List[str] = [],
    order_by: Optional[str] = None,
    relations: Optional[List[str]] = None,
    paginate: bool = False,
    page: int = 1,
    page_size: int = 10,
    distinct: Optional[str] = None,
    **kwargs,
) -> Union[Select, List[T], dict]:
    try:
        query = select(cls)

        # 1) eager‑load relasi hanya jika diminta
        if relations:
            query = apply_relations(query, cls, relations)

        # 2) keyword search
        query = _apply_keyword_search(query, cls, keyword, search_fields)

        # 3) filter absolut
        query = apply_filters(query, cls, **kwargs)

        # 4) order by
        if order_by:
            query = cls._apply_order_by(query, order_by)
        elif paginate:
            query = cls._apply_order_by(query, "id")

        # 5) DISTINCT custom (opsional)
        if distinct:
            query = query.distinct(getattr(cls, distinct))

        # -------------------- TANPA PAGINASI --------------------
        if not paginate:
            # harus di‑await agar menghasilkan async‑iterator
            stream = await db.stream_scalars(query)
            return [obj async for obj in stream]

        # -------------------- DENGAN PAGINASI -------------------
        pk_col = getattr(cls, "id", None) or inspect(cls).primary_key[0]
        count_q = select(func.count(func.distinct(pk_col))).select_from(cls)
        count_q = _apply_keyword_search(count_q, cls, keyword, search_fields)
        count_q = apply_filters(count_q, cls, **kwargs)
        total_items: int = await db.scalar(count_q)

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        items = result.unique().scalars().all()

        total_pages = (total_items + page_size - 1) // page_size if page_size else 0

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total_items,
            "pages": total_pages,
        }

    except Exception as e:
        raise RuntimeError(f"Error searching {cls.__name__}: {e}") from e
