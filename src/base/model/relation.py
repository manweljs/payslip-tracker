from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlalchemy.inspection import inspect
from typing import List, Optional, Type, Union
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .utils import camel_to_snake
from .serializer import Serializer


async def fetch_related(
    self,
    db: AsyncSession,
    relations: Optional[Union[str, List[str]]] = None,
    serialize: bool = False,
) -> Optional[SQLModel]:
    """
    Load the given relations eagerly using selectinload recursively
    and return the same instance.

    Args:
        db (AsyncSession): SQLAlchemy database session (async).
        relations (Optional[Union[str, List[str]]]): List of relations or comma-separated string.
            Can use '__' or '.' notation for nested relations.
        serialize (bool, optional): If True, return the serialized result.
            Default: False.

    Returns:
        Optional[SQLModel]: Instance with loaded relations, or
        dictionary if serialize is True.

    Raises:
        HTTPException: If instance not found.

    """

    # Jika relations berupa string, pisahkan berdasarkan koma.
    if isinstance(relations, str):
        relations = [rel.strip() for rel in relations.split(",")]

    # Jika relations disediakan, ganti '.' dengan '__' dan konversi ke snake_case.
    if relations:
        relations = [camel_to_snake(rel.replace(".", "__")) for rel in relations]

    # Jika tidak ada relations yang diberikan, ambil semua nama relasi dari model.
    if not relations:
        relations = [rel.key for rel in inspect(self.__class__).relationships]

    # Buat query untuk mengambil instance berdasarkan id.
    query = select(self.__class__).where(self.__class__.id == self.id)

    # Bangun load options berdasarkan daftar relations.
    try:
        load_options = build_load_options(self.__class__, relations)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if load_options:
        query = query.options(*load_options)

    # Eksekusi query secara asinkron.
    result = await db.execute(query)
    instance = result.scalars().first()

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{self.__class__.__name__} not found",
        )

    # Jika serialize True, kembalikan hasil yang diserialisasi.
    if serialize:
        return Serializer.serialize(instance, relations)

    return instance


def apply_relations(query, cls, relations: List[str] = None):
    """
    Utility function to add eager loading for relations.
    Handles both simple and nested relations using '.' or '__' as separators.

    Args:
        query: SQLAlchemy query object.
        cls: SQLModel model class.
        relations: List of relations with '__' or '.' as separators for nested relations.
            Accepts both snake_case and camelCase relation names.
    """
    if relations:
        relations = [camel_to_snake(rel) for rel in relations]
        for relation in relations:
            # Support nested relations with '__' or '.' as separator
            if "__" in relation:
                nested_relations = relation.split("__")
            elif "." in relation:
                nested_relations = relation.split(".")
            else:
                nested_relations = [relation]

            current_cls = cls
            load_option = None
            for rel in nested_relations:
                try:
                    relationship = getattr(current_cls, rel)
                except AttributeError:
                    raise ValueError(f"Relation '{rel}' not found in {cls.__name__}")

                if load_option is None:
                    load_option = selectinload(relationship)
                else:
                    load_option = load_option.selectinload(relationship)

                # Move to the next level of the relationship
                current_cls = relationship.property.mapper.class_

            query = query.options(load_option)
    return query


def build_load_options(cls: Type[SQLModel], relations: List[str]):
    """
    Build SQLAlchemy load options based on a list of relations with '__' notation.

    Args:
        cls (Type[SQLModel]): Main SQLAlchemy model class.
        relations (List[str]): List of relations with '__' notation for nested relations.

    Returns:
        List: List of appropriate SQLAlchemy load options.

    """
    load_options = []
    for relation in relations:
        parts = relation.split("__")
        if not parts:
            continue  # Lewati jika relation kosong

        # Mulai dengan pemuatan relation pertama
        try:
            attr = getattr(cls, parts[0])
        except AttributeError:
            raise ValueError(
                f"Relation '{parts[0]}' not found on model '{cls.__name__}'"
            )

        option = selectinload(attr)

        current_cls = attr.property.mapper.class_

        # Tambahkan pemuatan bertingkat untuk setiap bagian selanjutnya
        for part in parts[1:]:
            try:
                next_attr = getattr(current_cls, part)
            except AttributeError:
                raise ValueError(
                    f"Relation '{part}' not found on model '{current_cls.__name__}'"
                )

            option = option.selectinload(next_attr)
            current_cls = next_attr.property.mapper.class_

        load_options.append(option)

    return load_options


async def extend(
    self,
    db: AsyncSession,
    relation_name: str,
    items: Union[SQLModel, List[SQLModel]],
    commit: bool = True,
    overwrite: bool = False,
) -> None:
    """
    Add one or more items to the relation on the model instance.

    Args:
        db (AsyncSession): SQLAlchemy database session.
        relation_name (str): Name of the relation attribute on the model.
        items (Union[SQLModel, List[SQLModel]]): Object or list of objects to add to the relation.
        overwrite (bool, optional): If True, all existing items in the relation will be removed
            first, then new items will be added. Default is False.
        commit (bool, optional): Commit the changes to the database. Default is True.

    Raises:
        AttributeError: If relation name not found on model.
        TypeError: If relation does not support extend operation.
        HTTPException: If there is an error during item addition.
    """
    # Pastikan items selalu dalam bentuk list
    if not isinstance(items, list):
        items = [items]

    # Dapatkan atribut relation dari model saat ini
    try:
        relation = getattr(self, relation_name)
    except AttributeError as e:
        print(
            f"Error: Relation '{relation_name}' not found on model '{self.__class__.__name__}': {e}"
        )
        raise

    # Inisialisasi relation jika None
    if relation is None:
        relation = []
        setattr(self, relation_name, relation)

    # Pastikan relation mendukung operasi list
    if not hasattr(relation, "extend") or not hasattr(relation, "clear"):
        raise TypeError(
            f"Relation '{relation_name}' on model '{self.__class__.__name__}' "
            f"must be a list or support list operations (extend, clear, etc)."
        )

    # Jika overwrite=True, bersihkan relasi lama
    if overwrite:
        # Ini akan menghapus hubungan many-to-many di table asosiatif
        relation.clear()

    # Tambahkan item baru
    try:
        relation.extend(items)
    except Exception as e:
        print(f"Error during extend operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extending items: {str(e)}",
        )

    # Pastikan instance di-add ke sesi untuk merefleksikan perubahan
    db.add(self)

    # Commit atau flush perubahan sesuai parameter
    try:
        if commit:
            await db.commit()
            await db.refresh(self)
        else:
            await db.flush()
            await db.refresh(self)
    except Exception as e:
        print(f"Error during database operation: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extending items: {str(e)}",
        )


async def remove(
    self,
    db: AsyncSession,
    relation_name: str,
    items: Union[SQLModel, List[SQLModel]],
    commit: bool = True,
) -> None:
    """
    Delete one or more items from the relation on the model instance.

    Args:
        db (AsyncSession): SQLAlchemy database session.
        relation_name (str): Name of the relation attribute on the model.
        items (Union[SQLModel, List[SQLModel]]): Object or list of objects to remove from the relation.
        commit (bool, optional): Commit the changes to the database. Default is True.

    Raises:
        AttributeError: If relation name not found on model.
        TypeError: If relation does not support remove operation.
        RuntimeError: If there is an error during item removal.
    """
    # Pastikan items selalu dalam bentuk list
    if not isinstance(items, list):
        items = [items]

    # Dapatkan atribut relation dari model saat ini
    try:
        relation = getattr(self, relation_name)
    except AttributeError:
        raise AttributeError(
            f"Relation '{relation_name}' not found on model '{self.__class__.__name__}'."
        )

    # Validasi apakah relation mendukung penghapusan item
    if not isinstance(relation, list):
        raise TypeError(
            f"Relation '{relation_name}' on model '{self.__class__.__name__}' must be a list that support list operations."
        )

    # Hapus item dari relation jika ada
    for item in items:
        if item in relation:
            relation.remove(item)

    # Tambahkan instance ke sesi database
    db.add(self)

    # Commit atau flush perubahan sesuai dengan parameter
    try:
        if commit:
            await db.commit()
            await db.refresh(self)
        else:
            await db.flush()
            await db.refresh(self)
    except Exception as e:
        err = f"Error removing items: {e}"
        await db.rollback()
        raise RuntimeError(err)
