from sqlalchemy.orm import aliased
from sqlalchemy.sql import and_, or_, func
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Date
from typing import Optional, Union, List

# Tipe generik untuk SQLModel
# supported_operators
supported_operators = {
    "eq",  # equal (=)
    "lt",  # less than (<)
    "gt",  # greater than (>)
    "lte",  # less than or equal (<=)
    "gte",  # greater than or equal (>=)
    "ne",  # not equal (!=)
    "in",  # in (IN)
    "like",  # like (LIKE)
    "ilike",  # ilike (ILIKE)
    "date",  # date (DATE)
    "notin",  # not in (NOT IN)
    "lowerin",  #  lowerin (LOWER IN)
    "exists",  #  exists (EXISTS)
}


class Q:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connector = and_

    def __and__(self, other):
        return QGroup([self, other], and_)

    def __or__(self, other):
        return QGroup([self, other], or_)

    def build(self, model, aliases=None):
        """
        Membangun klausa WHERE dari field__operator=nilai
        dengan mendukung relasi. Contoh:
            Q(worksite__department__name__ilike="IT%")
            Q(end_date__gt=datetime.now())
        """
        conditions = []
        if aliases is None:
            aliases = {}

        for field, value in self.kwargs.items():

            # Pisahkan berdasarkan '__'
            parts = field.split("__")

            if len(parts) > 1 and parts[-1] in supported_operators:
                operator = parts[-1]
                column_name = parts[-2]
                relations = parts[:-2]
            else:
                operator = "eq"
                column_name = parts[-1]
                relations = parts[:-1]


            current_model = model
            for relation in relations:
                if relation not in aliases:
                    try:
                        related_model = getattr(
                            current_model, relation
                        ).property.mapper.class_
                        alias = aliased(related_model)
                        aliases[relation] = alias
                        current_model = alias
                    except AttributeError as e:
            
                        raise
                else:
                    current_model = aliases[relation]

            try:
                column = getattr(current_model, column_name)
         
            except AttributeError as e:
                raise e

            if operator == "eq":
                conditions.append(column == value)
            elif operator == "ne":
                conditions.append(column != value)
            elif operator == "lt":
                conditions.append(column < value)
            elif operator == "lte":
                conditions.append(column <= value)
            elif operator == "gt":
                conditions.append(column > value)
            elif operator == "gte":
                conditions.append(column >= value)
            elif operator == "in":
                if not isinstance(value, (list, tuple, set)):
                    value = [value]
                if None in value:
                    value = [v for v in value if v is not None]
                    conditions.append(or_(column.in_(value), column.is_(None)))
                    # print(f"[DEBUG] Condition: {column} IN {value} OR IS NULL")
                else:
                    conditions.append(column.in_(value))
                    # print(f"[DEBUG] Condition: {column} IN {value}")
            # elif operator == "notin":
            #     if not isinstance(value, (list, tuple, set)):
            #         value = [value]
            #     if None in value:
            #         value = [v for v in value if v is not None]
            #         conditions.append(and_(~column.in_(value), column.isnot(None)))
            #     else:
            #         conditions.append(~column.in_(value))
            elif operator == "notin":
                if not isinstance(value, (list, tuple, set)):
                    value = [value]

                # Jika user memang memasukkan None dalam value,
                # berarti user mau men-EXCLUDE baris dengan kolom = None juga.
                if None in value:
                    # Kita buang None dari value agar tidak error di column.in_(...)
                    value = [v for v in value if v is not None]
                    # Di sini: baris != value, dan juga kolom != NULL
                    conditions.append(and_(~column.in_(value), column.isnot(None)))
                else:
                    # Jika None TIDAK ada di value, kita mau baris NULL tetap ikut.
                    # Caranya: (column IS NULL) OR (column NOT IN (value))
                    conditions.append(or_(column.is_(None), ~column.in_(value)))
            elif operator == "like":
                conditions.append(column.like(value))
            elif operator == "ilike":
                conditions.append(column.ilike(value))
            elif operator == "lowerin":
                if not isinstance(value, (list, tuple, set)):
                    value = [value]
                lowered = [v.lower() for v in value]
                conditions.append(func.lower(column).in_(lowered))
            elif operator == "exists":
                # value diharapkan boolean True/False
                # jika True => relasi harus ada isinya => column.any()
                # jika False => relasi harus kosong => ~column.any()
                if value:
                    conditions.append(column.any())
                else:
                    conditions.append(~column.any())
            else:
                raise ValueError(f"Operator '{operator}' tidak didukung.")

        return self.connector(*conditions)


class QGroup:
    def __init__(self, queries, connector):
        self.queries = queries
        self.connector = connector

    def __and__(self, other):
        if isinstance(other, (Q, QGroup)):
            # satukan jika connector sama-sama AND
            if self.connector is and_:
                queries = self.queries + (
                    other.queries if isinstance(other, QGroup) else [other]
                )
                return QGroup(queries, and_)
            return QGroup([self, other], and_)
        return NotImplemented

    def __or__(self, other):
        if isinstance(other, (Q, QGroup)):
            if self.connector is or_:
                queries = self.queries + (
                    other.queries if isinstance(other, QGroup) else [other]
                )
                return QGroup(queries, or_)
            return QGroup([self, other], or_)
        return NotImplemented

    def build(self, model, aliases=None):
        if aliases is None:
            aliases = {}
        conds = [q.build(model, aliases) for q in self.queries]
        return self.connector(*conds)


def apply_filters(query, cls, filters: Optional[Union[Q, QGroup]] = None, **kwargs):
    """
    Fungsi apply_filters untuk menambahkan klausa where ke query SQLAlchemy
    berdasarkan Q atau QGroup, serta filter biasa dalam bentuk kwargs.
    """
    aliases = {}

    # 1) Jika ada param `filters` (Q/QGroup), kita build dulu
    # if filters is not None and isinstance(filters, (Q, QGroup)):
    #     query = query.where(filters.build(cls, aliases))
    if filters is not None and isinstance(filters, (Q, QGroup)):
        # build kondisi dan kumpulkan aliases relasi
        where_clause = filters.build(cls, aliases)

        # tambahkan JOIN untuk setiap relasi yang di‐alias
        for relation, alias in aliases.items():
            query = query.join(alias, getattr(cls, relation))

        query = query.where(where_clause)

    # 2) Proses kwargs satu per satu
    for field, value in kwargs.items():
        if not field:
            raise ValueError("Filter field tidak boleh kosong.")

        parts = field.split("__")
        if len(parts) == 0:
            raise ValueError("Filter field tidak boleh kosong.")

        # Mirip logika di atas:
        if len(parts) > 1 and parts[-1] in supported_operators:
            operator = parts[-1]
            actual_field = parts[-2]
            relations = parts[:-2]
        else:
            operator = "eq"
            actual_field = parts[-1]
            relations = parts[:-1]

        if not actual_field:
            raise ValueError(f"Field aktual kosong dalam filter '{field}'.")

        current_cls = cls
        current_query = query

        # Join relasi jika ada
        for relation in relations:
            if not relation:
                raise ValueError(f"Bagian relasi kosong dalam filter '{field}'.")
            if relation not in aliases:
                related_model = getattr(current_cls, relation).property.mapper.class_
                alias = aliased(related_model)
                aliases[relation] = alias
                current_query = current_query.join(
                    alias, getattr(current_cls, relation)
                )
                current_cls = alias
            else:
                alias = aliases[relation]
                current_query = current_query.join(
                    alias, getattr(current_cls, relation)
                )
                current_cls = alias

        # Ambil kolom
        try:
            column = getattr(current_cls, actual_field)
        except AttributeError:
            raise ValueError(
                f"Field '{actual_field}' tidak valid untuk model '{current_cls.__name__}'"
            )

        # Bangun kondisi
        if operator == "eq":
            condition = column == value
        elif operator == "ne":
            condition = column != value
        elif operator == "lt":
            condition = column < value
        elif operator == "lte":
            condition = column <= value
        elif operator == "gt":
            condition = column > value
        elif operator == "gte":
            condition = column >= value
        elif operator == "in":
            if not isinstance(value, (list, tuple, set)):
                value = [value]
            if None in value:
                value = [v for v in value if v is not None]
                condition = or_(column.in_(value), column.is_(None))
            else:
                condition = column.in_(value)
        # elif operator == "notin":
        #     if not isinstance(value, (list, tuple, set)):
        #         value = [value]
        #     if None in value:
        #         value = [v for v in value if v is not None]
        #         condition = and_(~column.in_(value), column.isnot(None))
        #     else:
        #         condition = ~column.in_(value)
        elif operator == "notin":
            if not isinstance(value, (list, tuple, set)):
                value = [value]

            # Jika user memang menyebut `None` di dalam value,
            # maka "None" pun ikut dikecualikan.
            if None in value:
                # Buang None agar aman di query `~column.in_(value)`,
                # lalu tambahkan syarat `column.isnot(None)` supaya baris None ikut ter‐exclude.
                value = [v for v in value if v is not None]
                condition = and_(
                    ~column.in_(value),
                    column.isnot(None),
                )
            else:
                # Jika user TIDAK menyebut None,
                # baris None tetap di‐include.
                # (kolom IS NULL) OR (kolom NOT IN (value))
                condition = or_(
                    column.is_(None),
                    ~column.in_(value),
                )

        elif operator == "like":
            condition = column.like(value)
        elif operator == "ilike":
            condition = column.ilike(value)
        elif operator == "lowerin":
            if not isinstance(value, (list, tuple, set)):
                value = [value]
            lowered = [v.lower() for v in value]
            condition = func.lower(column).in_(lowered)
        elif operator == "exists":
            # True => relasi tidak kosong => any()
            # False => relasi kosong => ~any()
            if value:
                condition = column.any()
            else:
                condition = ~column.any()
        else:
            raise ValueError(f"Operator '{operator}' tidak didukung.")

        current_query = current_query.where(condition)
        query = current_query

    return query
