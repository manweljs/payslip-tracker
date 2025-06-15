from fastapi import HTTPException, status
from sqlmodel import SQLModel
from typing import List, Optional, TypeVar, Type, Union
from sqlalchemy import asc, desc, func, or_, and_, delete
from sqlalchemy.sql.selectable import Select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.inspection import inspect
from hashlib import sha256
import tracemalloc
from .utils import camel_to_snake
from .search import _search


from .serializer import Serializer
from .filter import Q, QGroup, apply_filters
from .relation import (
    apply_relations,
    build_load_options,
    extend as _extend,
    remove as _remove,
)


tracemalloc.start()

# Tipe generik untuk SQLModel
T = TypeVar("T", bound="BaseModel")


class BaseModel(SQLModel):
    async def extend(
        self,
        db: AsyncSession,
        relation_name: str,
        items: Union[SQLModel, List[SQLModel]],
        commit: bool = True,
        overwrite: bool = False,
    ) -> None:
        """
        Add items to the relation on the model.

        Args:
            db (AsyncSession): Asynchronous database session.
            relation_name (str): Name of the relation to extend.
            items (Union[SQLModel, List[SQLModel]]): Item or list of items to add to the relation.
            commit (bool): Flag to commit the transaction.
            overwrite (bool): Flag to overwrite the existing relation.

        Returns:
            None

        Raises:
            AttributeError:If relation name not found on model.
            TypeError:If relation does not support extend operation.
            HTTPException:If there is an error during item addition.

        """
        return await _extend(self, db, relation_name, items, commit, overwrite)

    async def remove(
        self,
        db: AsyncSession,
        relation_name: str,
        items: Union[SQLModel, List[SQLModel]],
        commit: bool = True,
    ):
        """
        Menghapus item dari relasi pada model.
        """
        return await _remove(self, db, relation_name, items, commit)

    @classmethod
    async def count(
        cls: Type[T],
        db: AsyncSession,
        filters: Optional[Union[Q, QGroup]] = None,
        **kwargs,
    ) -> int:
        """
        Count the number of rows based on the given filter.

        Args:
            db (AsyncSession): Asynchronous database session.
            filters (Optional[Union[Q, QGroup]]): Filter based on Q or QGroup.
            **kwargs: Additional filters based on field and operator.

        Returns:
            int: Number of rows that match the filter.
        """
        query = select(func.count()).select_from(cls)

        # Tambahkan filter berbasis kwargs atau Q
        query = apply_filters(query, cls, filters=filters, **kwargs)

        # Eksekusi query untuk menghitung
        result = await db.scalar(query)
        return result

    @classmethod
    async def create_or_update(
        cls: Type[T],
        db: AsyncSession,
        obj_in: Union[T, dict],
        commit: bool = True,
    ) -> T:
        """
        Create or update an object in the database based on the provided data.
        If the object already exists, update it. Otherwise, create a new object.

        Args:
            db (AsyncSession): Asynchronous database session.
            obj_in (Union[T, dict]): Input data for the object.
            commit (bool): Flag to commit the transaction.

        Returns:
            T: Created or updated object

        """

        async def commit_and_refresh(obj):
            """Helper untuk commit atau flush dan refresh objek."""
            if commit:
                await db.commit()
            else:
                await db.flush()
            await db.refresh(obj)

        # Konversi obj_in ke dictionary jika perlu
        if isinstance(obj_in, dict):
            obj_data = obj_in
        else:
            obj_data = obj_in.model_dump(exclude_unset=True)

        obj_id = obj_data.get("id", None)
        if obj_id is not None:
            # Mencari objek yang sudah ada berdasarkan id
            existing_obj = await db.get(cls, obj_id)
            if existing_obj:
                # Update objek yang sudah ada
                for field, value in obj_data.items():
                    setattr(existing_obj, field, value)
                db.add(existing_obj)
                await commit_and_refresh(existing_obj)
                return existing_obj
            else:
                # Jika tidak ditemukan, buat objek baru dengan id tersebut
                new_obj = cls(**obj_data)
                db.add(new_obj)
                await commit_and_refresh(new_obj)
                return new_obj
        else:
            # Jika tidak ada id, buat objek baru
            new_obj = cls(**obj_data)
            db.add(new_obj)
            await commit_and_refresh(new_obj)
            return new_obj

    async def save(
        self,
        db: AsyncSession,
        commit: bool = True,
        relations: Optional[List[str]] = False,
        serialize: bool = False,
    ) -> Union["BaseModel", dict]:
        """
        Save model instance to the database.
        Optionally load relations using `fetch_related`.

        Args:
            db (AsyncSession): SQLAlchemy database session.
            commit (bool): Flag to commit the transaction.
            relations (Optional[List[str]]): List of relations to load using `fetch_related`.
            serialize (bool): If True, serialize the result. Defaults to False.

        Returns:
            Instance with relations loaded if provided. If `serialize=True`, return serialized data.

        :rtype: Union[BaseModel, dict]
        """
        # Tambahkan instance ke sesi hanya jika belum ada di identity_map
        if self not in db.identity_map.values():
            db.add(self)

        # Commit atau flush perubahan
        if commit:
            await db.commit()
            await db.refresh(self)
        else:
            await db.flush()
            await db.refresh(self)

        # Muat relasi menggunakan fetch_related jika diperlukan
        if relations:
            return await self.fetch_related(db, relations, serialize)

        return self

    @classmethod
    async def create(
        cls: Type[T],
        db: AsyncSession,
        obj_in: Union[T, dict],
        commit: bool = True,
        exclude: Optional[List[str]] = None,
        relations: Optional[List[str]] = None,
    ) -> T:
        """
        Create a new object in the database, with an option to exclude certain columns.
        Optionally load relations if `relations` are provided.

        Args:
            db (AsyncSession): Asynchronous database session.
            obj_in (Union[T, dict]): Input data for the object.
            commit (bool): Flag to commit the transaction.
            exclude (Optional[List[str]]): List of columns to exclude.
            relations (Optional[List[str]]): List of relationships to load.

        Returns:
            T: Created object

        """
        exclude = exclude or []

        if not obj_in:
            raise ValueError("obj_in is required for create")

        # Jika `obj_in` adalah dict, buang kolom yang ada dalam `exclude`
        if isinstance(obj_in, dict):
            obj_in = {key: value for key, value in obj_in.items() if key not in exclude}

        # Membuat instance dari model
        obj = cls(**obj_in) if isinstance(obj_in, dict) else obj_in
        db.add(obj)

        if commit:
            await db.commit()
            await db.refresh(obj)
        else:
            await db.flush()
            await db.refresh(obj)

        # Muat relasi jika disediakan
        if relations:
            obj = await obj.fetch_related(db, relations=relations, serialize=False)

        return obj

    @classmethod
    async def get(
        cls: Type[T],
        db: AsyncSession,
        filters: Optional[Union[Q, QGroup]] = None,
        relations: Optional[Union[List[str], bool]] = None,
        **kwargs,
    ) -> Optional[T]:
        """
        Get a single item from the database with the given filter.
        Optionally load relations using `relations`.

        Args:
            db (AsyncSession): SQLAlchemy database session.
            relations (Optional[List[str]]): List of relationships to load.
            **kwargs: Additional filters for the search.

        Returns:
            Optional[T]: Model instance if found or None.

        Raises:
            ValueError: If the field is not found in the model.
            RuntimeError: If an error occurs while executing the query.
        """
        query = select(cls)

        # Auto-detect all relationships if `relations` is None
        # if relations is None and relations is not False:
        #     relations = [rel.key for rel in inspect(cls).relationships]

        # Apply eager loading
        query = apply_relations(query, cls, relations)

        # Apply filters
        query = apply_filters(query, cls, filters=filters, **kwargs)
        # for field, value in kwargs.items():
        #     try:
        #         query = query.where(getattr(cls, field) == value)
        #     except AttributeError as e:
        #         raise ValueError(f"Field '{field}' not found in {cls.__name__}") from e

        # Execute query
        try:
            result = await db.execute(query)
            return result.scalars().first()
        except Exception as e:
            raise RuntimeError(f"Error executing `get` query: {e}") from e

    @classmethod
    async def get_or_create(
        cls: Type[T],
        db: AsyncSession,
        defaults: Optional[dict] = None,
        relations: Optional[List[str] | bool] = False,
        commit: bool = True,
        **kwargs,
    ) -> T:
        """
        Get an item from the database with a specific filter.
        If not found, create a new item with the `defaults` and `kwargs` data.

        Args:
            db (AsyncSession): Asynchronous database session.
            defaults (Optional[dict]): Default data for the new item.
            relations (Optional[List[str]]): List of relationships to load.
            commit (bool): Flag to commit the transaction.
            **kwargs: Additional filters for the search.

        Returns:
            T: Model instance

        """

        # 1. Coba dapatkan data dengan filter yang diberikan (beserta relasi)
        item = await cls.get(db, relations=relations, **kwargs)
        if item:
            # Jika ditemukan, relasi sudah dimuat oleh cls.get (karena kita kirim relations ke sana)
            return item

        # 2. Siapkan data untuk objek baru
        if defaults is None:
            defaults = {}
        data = {**kwargs, **defaults}

        # 3. Buat objek baru
        new_obj = cls(**data)
        db.add(new_obj)

        # 4. Commit/flush lalu refresh
        if commit:
            await db.commit()
            await db.refresh(new_obj)
        else:
            await db.flush()
            await db.refresh(new_obj)

        # 5. Muat relasi untuk objek baru (jika ada)
        if relations:
            new_obj = await new_obj.fetch_related(
                db, relations=relations, serialize=False
            )

        return new_obj

    @classmethod
    async def all(
        cls: Type[T],
        db: AsyncSession,
        relations: Optional[List[str] | bool] = None,
        order_by: Optional[str] = None,
    ) -> List[T]:
        """
        Get all data from the model with optional order_by using AsyncSession.

        Args:
            db (AsyncSession): Asynchronous database session.
            relations (Optional[List[str]]): List of relationships for eager loading.
            order_by (Optional[str]): Field name to order the results by.

        Returns:
            List[T]: List of model instances.

        """
        query = select(cls)

        # if relations is None and relations is not False:
        #     relations = [rel.key for rel in inspect(cls).relationships]

        query = apply_relations(query, cls, relations)

        # Tambahkan pengurutan jika parameter order_by diberikan
        if order_by:
            query = cls._apply_order_by(query, order_by)

        # Eksekusi query secara asinkron
        result = await db.execute(query)
        # Gunakan unique() jika relasi dilibatkan, scalars() untuk query standar
        return result.unique().scalars().all()

    @classmethod
    async def get_all(
        cls: Type[T],
        db: AsyncSession,
        relations: Optional[List[str] | bool] = None,
        order_by: Optional[str] = None,
    ) -> List[T]:
        """
        Get all data from the model with optional order_by using AsyncSession.

        Args:
            db (AsyncSession): Asynchronous database session.
            order_by (Optional[str]): Field name to order the results by.

        Returns:
            List[T]: List of model instances.
        """
        # Metode ini identik dengan `all`, dapat menggunakan logika yang sama
        return await cls.all(db, order_by=order_by, relations=relations)

    @classmethod
    async def search(
        cls: Type[T],
        db: AsyncSession,
        keyword: Optional[str] = None,
        search_fields: List[str] = [],
        order_by: Optional[str] = None,
        relations: Optional[List[str]] = None,  # Opsi prefetch_related
        # -- Pagination --
        paginate: bool = False,
        page: int = 1,
        page_size: int = 10,
        distinct: Optional[str] = None,
        **kwargs,
    ) -> Union[Select, List[T], dict]:
        """
        Searches for data from the model with support for eager loading, keyword search,
        ordering, distinct, and pagination.

        This function performs a query on the model based on the provided parameters.
        It operates in two modes:
        - Without pagination (paginate=False): Returns a list of model instances.
        - With pagination (paginate=True): Returns a dictionary containing pagination info
            along with the list of queried items.

        Parameters:
            db (AsyncSession): Asynchronous database session used to execute the query.
            keyword (Optional[str]): The keyword used for searching.
            search_fields (List[str]): A list of field names to search using the keyword.
            order_by (Optional[str]): The field name to order the results by. Prefix '-' for descending order.
            relations (Optional[List[str]]): A list of relationship names for eager loading. Defaults to all relationships if None.
            paginate (bool): If True, activates pagination mode and returns the result as a dictionary.
            page (int): The current page number to display (default is 1).
            page_size (int): The number of items per page (default is 10).
            distinct (Optional[str]): The field name to use for eliminating duplicate results.

        Returns:
            If paginate=False, returns List[T] containing the model instances.
            If paginate=True, returns a dictionary with the structure:
            {
                "items": List[T],      # List of model instances from the query
                "page": int,           # Current page number
                "page_size": int,      # Number of items per page
                "total": int,          # Total number of items matching the search criteria
                "pages": int           # Total number of pages (ceiling of total/page_size)
            }
        """
        return await _search(
            cls=cls,
            db=db,
            keyword=keyword,
            search_fields=search_fields,
            order_by=order_by,
            relations=relations,
            paginate=paginate,
            page=page,
            page_size=page_size,
            distinct=distinct,
            **kwargs,
        )

    @classmethod
    async def update(
        cls: Type[T],
        db: AsyncSession,
        db_obj: T,
        obj_in: Union[T, dict],
        relations: Optional[List[str]] = None,
        commit: bool = True,
    ) -> T:
        """
        Memperbarui objek yang ada dalam database.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump()

        mapper = inspect(db_obj).mapper
        pk_keys = {col.key for col in mapper.primary_key}

        for field, value in update_data.items():
            # lewati jika ini primary key
            if field in pk_keys:
                continue
            setattr(db_obj, field, value)

        # for field, value in update_data.items():
        #     setattr(db_obj, field, value)

        db.add(db_obj)
        if commit:
            await db.commit()
            await db.refresh(db_obj)
        else:
            await db.flush()

        if relations:
            db_obj = await db_obj.fetch_related(db, relations=relations)
        return db_obj

    async def delete(
        self,
        db: AsyncSession,
        commit: bool = True,
        force: bool = False,
    ) -> None:
        """
        Delete the object from the database.

        Args:
            db (AsyncSession): An asynchronous database session to perform the deletion operation.
            commit (bool): Determine whether the changes should be committed after deletion.
                Default is True.
            force (bool): Determine whether the deletion should be done with direct SQL query.
                Default is False.

        Examples:
        --------
        Default deletion (using ORM):
            ```
            await some_object.delete(db)
            await some_object.delete(db, force=True)
            await some_object.delete(db, force=True, commit=False)
            ```
        """

        # NOTE:
        # - Jika `force=True`, metode ini akan menghapus objek menggunakan query SQL langsung:
        #     `DELETE FROM <tabel> WHERE id=<id>`.
        # Ini lebih efisien untuk kasus dengan relasi kompleks atau ketika constraint
        # ON DELETE CASCADE diaktifkan.
        # - Jika `force=False`, ORM akan mengelola penghapusan data secara manual,
        # termasuk memuat dan memproses data terkait jika relasi diatur demikian.
        # ------
        # - Gunakan `force=True` jika penghapusan default menghasilkan error atau jika Anda
        # yakin constraint ON DELETE CASCADE | SET NULL di database sudah diatur dengan benar.
        # - Hindari penggunaan `force=True` jika relasi kompleks dikelola secara manual oleh ORM,
        # karena penghapusan langsung dapat menyebabkan data terkait tidak sinkron.

        if force:
            # Gunakan SQL langsung
            await db.execute(delete(type(self)).where(type(self).id == self.id))
        else:
            # Gunakan penghapusan default ORM
            await db.delete(self)
        if commit:
            await db.commit()
        else:
            await db.flush()

    @classmethod
    async def get_or_404(
        cls: Type[T],
        db: AsyncSession,
        relations: Optional[Union[List[str], bool]] = None,
        **kwargs,
    ) -> Optional[T]:
        """
        Get a single item based on filter. If not found, raise HTTPException.

        Args:
            :db (AsyncSession): SQLAlchemy database session.
            :**kwargs: Additional filters for the search.

        Returns:
            Optional[T]: Model instance if found.

        Raises:
            HTTPException: If model is not found.
        """
        item = await cls.get(db, **kwargs, relations=relations)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{cls.__name__} not found",
            )
        return item

    @classmethod
    async def get_or_None(
        cls: Type[T],
        db: AsyncSession,
        relations: Optional[Union[str, List[str]]] = None,
        filters: Optional[Union[Q, QGroup]] = None,
        **kwargs,
    ) -> Optional[T]:
        """
        Get a single item based on filter. If not found, return None.

        Args:
            db (AsyncSession): SQLAlchemy database session.
            relations (Optional[Union[str, List[str]]]): List of relationships to load.
            **kwargs: Additional filters for the search.

        Returns:
            Optional[T]: Model instance if found or None.

        """

        item = await cls.get(db, **kwargs, relations=relations, filters=filters)
        if not item:
            return None
        return item

    async def fetch_related(
        self,
        db: AsyncSession,
        relations: Optional[Union[str, List[str]]] = None,
        serialize: bool = False,
    ) -> Optional["BaseModel"]:
        """
        Memuat relasi yang diberikan menggunakan selectinload bertingkat dan mengembalikan instance yang sama.

        Args:
            db (AsyncSession): Sesi database SQLAlchemy.
            relations (List[str]): Daftar relasi dengan notasi '__' untuk relasi bertingkat.
            serialize (bool, optional): Apakah akan menyerialisasi hasilnya. Defaults to False.

        Returns:
            Optional[BaseModel]: Instance dengan relasi yang dimuat atau None jika tidak ditemukan.
        """

        if isinstance(relations, str):
            relations = [rel.strip() for rel in relations.split(",")]

        query = select(self.__class__).where(self.__class__.id == self.id)

        if not relations:
            relations = [rel.key for rel in inspect(self.__class__).relationships]

        query = apply_relations(query, self.__class__, relations)

        # try:
        #     load_options = build_load_options(self.__class__, relations)
        # except ValueError as e:
        #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # # Terapkan opsi pemuatan ke query
        # if load_options:
        #     query = query.options(*load_options)

        # Eksekusi query secara asinkron dan muat relasi
        result = await db.execute(query)
        instance = result.scalars().first()

        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.__class__.__name__} not found",
            )

        if serialize:
            return Serializer.serialize(instance, relations)
        return instance

    def prefetch_related(self, *relations: List[str]):
        """Menambahkan eager loading untuk relasi"""
        for relation in relations:
            self.query = self.query.options(
                selectinload(getattr(self.__class__, relation))
            )
        return self

    # @classmethod
    # def _apply_order_by(cls, query, order_by: str):
    #     """Menerapkan pengurutan berdasarkan kolom yang ditentukan dengan opsi ascending/descending"""
    #     if order_by.startswith("-"):
    #         order_column = getattr(cls, order_by[1:], None)  # Pengurutan descending
    #         if order_column is None:
    #             raise ValueError(
    #                 f"Order by column {order_by[1:]} is not a valid column for {cls.__name__}"
    #             )
    #         query = query.order_by(desc(order_column))
    #     else:
    #         order_column = getattr(cls, order_by, None)  # Pengurutan ascending
    #         if order_column is None:
    #             raise ValueError(
    #                 f"Order by column {order_by} is not a valid column for {cls.__name__}"
    #             )
    #         query = query.order_by(asc(order_column))
    #     return query

    @classmethod
    async def filter(
        cls: Type[T],
        db: AsyncSession,
        relations: Optional[Union[List[str], bool]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        serialize: Optional[bool] = False,
        filters: Optional[Union[Q, QGroup]] = None,
        cache_key: Optional[str] = None,
        ttl: Optional[int] = None,
        # -- Tambahkan parameter paginasi --
        paginate: bool = False,
        page: int = 1,
        page_size: int = 10,
        **kwargs,
    ) -> Union[List[T], dict]:
        """
        Retrieve multiple items with optional filtering, ordering, and eager loading,
        + caching support.
        + pagination support.

        Parameters
        ----------
        db: AsyncSession
            The SQLAlchemy asynchronous session to use for the query.
        relations: Optional[Union[List[str], bool]]
            A list of relationships to eager load. If None, all relationships will be loaded.
            If False, no relationships will be loaded.
        order_by: Optional[Union[str, List[str]]]
            The field name(s) to order the results by. If a string starts with '-', it will be ordered descending.
        serialize: Optional[bool]
            If True, the results will be serialized using the Serializer class.
            Defaults to False.
        filters: Optional[Union[Q, QGroup]]
            Filter based on Q or QGroup. If None, no filters will be applied.
        cache_key: Optional[str]
            If provided, the results will be cached with this key.
            If None, caching will not be applied.
        ttl: Optional[int]
            Time-to-live for the cache in seconds. Defaults to None (no expiration).
        paginate: bool
            If True, the results will be paginated. Defaults to False.
        page: int
            The current page number for pagination. Defaults to 1.
        page_size: int
            The number of items per page for pagination. Defaults to 10.
        **kwargs:
            Additional filters for the search, such as field=value pairs.

        Returns
        -------
        Union[List[T], dict]:
            If paginate=False, returns a list of model instances.
            If paginate=True, returns a dictionary with pagination info and items.


        Example
        -------
        If paginate=True, return a dictionary with the following structure:
        ```
            {
                "items": [...],
                "page": page,
                "page_size": page_size,
                "total": total_items,
                "pages": total_pages
            }
            ```

        """

        query = select(cls)

        # Auto-detect all relationships if `relations` is None
        # if relations is None and relations is not False:
        #     relations = [rel.key for rel in inspect(cls).relationships]
        # else:
        #     if relations is not False:
        #         relations = [camel_to_snake(rel) for rel in relations]

        # Apply eager loading
        query = apply_relations(query, cls, relations)

        # Apply filters
        query = apply_filters(query, cls, filters=filters, **kwargs)

        # Apply ordering
        if order_by:
            query = cls._apply_order_by(query, order_by)
        elif paginate:
            query = cls._apply_order_by(query, "id")

        # -- Jika tidak pakai pagination, jalankan logika lama (beserta cache) --
        if not paginate:
           

            # Execute query
            try:
                result = await db.execute(query)
                instances = result.unique().scalars().all()

                # Serialize results if requested
                if serialize:
                    serialized_data = [
                        Serializer.serialize(instance, relations)
                        for instance in instances
                    ]

                    return serialized_data


                return instances

            except Exception as e:
                raise RuntimeError(f"Error executing `filter` query: {e}") from e

        # -- Jika pakai pagination:
        # 1) Hitung total
        # 2) offset & limit
        # 3) Return dict dengan struktur paginasi
        else:
            # =============== HITUNG TOTAL ===============
            count_query = select(func.count()).select_from(cls)
            # Terapkan filter yg sama ke count_query
            count_query = apply_filters(count_query, cls, filters=filters, **kwargs)

            try:
                total_items = await db.scalar(count_query)
            except Exception as e:
                raise RuntimeError(f"Error counting items: {e}")

            # =============== OFFSET & LIMIT ===============
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

            # Jalankan query
            try:
                result = await db.execute(query)
                instances = result.unique().scalars().all()
            except Exception as e:
                raise RuntimeError(f"Error executing paginated `filter` query: {e}")

            # =============== Bikin response pagination ===============
            total_pages = 0
            if page_size > 0:
                total_pages = (total_items + page_size - 1) // page_size  # ceiling

            # Opsional: serialize item
            if serialize:
                items = [
                    Serializer.serialize(instance, relations) for instance in instances
                ]
            else:
                items = instances

            return {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total_items,
                "pages": total_pages,
            }

    @classmethod
    async def first(
        cls: Type[T],
        db: AsyncSession,
        filters: Optional[Union[Q, QGroup]] = None,
        relations: Optional[Union[List[str], bool]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        serialize: bool = False,
        cache_key: Optional[str] = None,
        ttl: int = 300,
        **kwargs,
    ) -> Optional[Union[dict, T]]:
        """
        Retrieve the first item from the database based on filters and relations.
        If `cache_key` is provided, it will cache the result for a specified time-to-live (ttl).

        Parameters
        ----------
        cls: Type[T]
            The class type of the model to query.
        db: AsyncSession
            The SQLAlchemy asynchronous session to use for the query.
        filters: Optional[Union[Q, QGroup]]
            Optional filters to apply to the query, can be a single Q or a QGroup.
        relations: Optional[Union[List[str], bool]]
            Optional list of relationships to eager load. If None, all relationships will be loaded.
        order_by: Optional[Union[str, List[str]]]
            Optional field(s) to order the results by. If None, no ordering is applied.
        serialize: bool
            If True, the result will be serialized into a dictionary format.
        fetch_policy: Optional[DB_FETCH_POLICY]
            Fetch policy for the query. Check the DB_FETCH_POLICY enum for options.
        cache_key: Optional[str]
            If provided, the result will be cached with this key.
        ttl: int
            Time-to-live for the cache in seconds. Default is 300 seconds (5 minutes).

        Returns
        -------
        Optional[Union[dict, T]]
            The first item that matches the filters and relations, serialized if `serialize` is True.

        """

        query = select(cls)

        query = apply_filters(query, cls, filters=filters, **kwargs)
        query = apply_relations(query, cls, relations)

        if order_by:
            query = cls._apply_order_by(query, order_by)

        result = await db.execute(query)
        instance = result.scalars().first()

        if instance and serialize:
            return Serializer.serialize(instance, relations)

        return instance

    @classmethod
    async def bulk_create(
        cls: Type[T],
        db: AsyncSession,
        objects_in: List[T],
        commit: bool = True,
    ) -> List[T]:
        """
        Bulk create objek dalam database dengan penanganan rollback.

        Args:
            db (AsyncSession): Instance sesi SQLAlchemy.
            objects_in (List[T]): Daftar objek yang akan dibuat.
            commit (bool, optional): Apakah akan melakukan commit setelah menambahkan objek. Defaults to True.

        Returns:
            List[T]: Daftar objek yang telah dibuat.
        """
        try:
            # Tambahkan semua objek ke sesi
            db.add_all(objects_in)

            if commit:
                await db.commit()
                # Refresh setiap objek untuk memastikan semua field terisi
                for obj in objects_in:
                    await db.refresh(obj)
            else:
                await db.flush()
                # Refresh setiap objek untuk memastikan semua field terisi
                for obj in objects_in:
                    await db.refresh(obj)

            return objects_in
        except Exception as e:
            # Rollback jika terjadi kesalahan
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Bulk create failed: {str(e)}",
            )

    @classmethod
    async def bulk_delete(
        cls: Type[T],
        db: AsyncSession,
        objects: List[T],
        commit: bool = True,
    ) -> None:
        """
        Menghapus beberapa objek dari database secara bulk berdasarkan daftar objek.

        Args:
            db (AsyncSession): Instance sesi SQLAlchemy.
            objects (List[T]): Daftar objek model yang akan dihapus.
            commit (bool, optional): Apakah akan melakukan commit setelah penghapusan. Defaults to True.

        Raises:
            HTTPException: Jika terjadi kesalahan selama penghapusan.
            ValueError: Jika objek tidak memiliki atribut 'id'.
        """
        if not objects:
            return  # Tidak ada yang dihapus jika daftar objek kosong

        try:
            # Ekstrak ID dari setiap objek
            object_ids = []
            for obj in objects:

                pk = obj.id
                object_ids.append(pk)

            # Pastikan ada ID yang diekstrak
            if not object_ids:
                raise ValueError(
                    "No valid IDs found in the provided objects for bulk delete."
                )

            # Lakukan operasi bulk delete menggunakan satu query SQL
            await db.execute(delete(cls).where(cls.id.in_(object_ids)))

            if commit:
                await db.commit()
            else:
                await db.flush()
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve),
            )
        except Exception as e:
            # Rollback jika terjadi kesalahan
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Bulk delete failed: {str(e)}",
            )

    @staticmethod
    def _generate_cache_key(
        cache_key: str, version: int, query: str, max_query_length: int = 500
    ) -> str:
        """
        Generate a unique cache key using cache_key, version, and a hashed truncated query.

        Args:
            cache_key (str): Key master untuk grup cache.
            version (int): Versi cache key.
            query (str): Query SQL yang di-hash.
            max_query_length (int): Panjang maksimal query sebelum di-hash.

        Returns:
            str: Cache key unik.
        """
        # Potong query jika panjangnya melebihi batas
        truncated_query = (
            query[:max_query_length] if len(query) > max_query_length else query
        )

        # Hash query yang sudah dipotong
        full_hash = sha256(truncated_query.encode()).hexdigest()

        # Ambil maksimal 64 karakter dari hasil hash
        safe_hash = full_hash[:64]

        # Gabungkan cache_key, version, dan hash untuk membuat key cache
        return f"{cache_key}:{version}:{safe_hash}"

    @classmethod
    def _apply_order_by(cls, query, order_by):
        """
        Menerapkan multiple order_by dengan format berikut:
        - Bisa single string ("kolom", "-kolom") maupun list(["kolom1", "-kolom2"]).
        - Prefix '-' menandakan descending.
        - Pemisah relasi boleh pakai '.' ataupun '__'
            (contoh: 'customer.city.name' atau 'customer__city__name').
        - Urutan item dalam list mencerminkan prioritas order.

        Contoh:
            order_by = "user__profile.full_name"
            order_by = "-user__profile__full_name"
            order_by = ["-stripe_transaction.created", "user__profile.full_name"]
        """
        if not order_by:
            return query

        # Jika single string, jadikan list agar lebih uniform.
        if isinstance(order_by, str):
            order_by = [order_by]

        for order_expr in order_by:
            descending = False
            expr = order_expr.strip()

            # Cek prefix '-'
            if expr.startswith("-"):
                descending = True
                expr = expr[1:]  # buang '-'

            # Ganti semua '.' menjadi '__' agar seragam
            expr = expr.replace(".", "__")

            # Pisahkan berdasarkan '__'
            path_parts = expr.split("__")

            # Bagian depan path adalah chain relasi, bagian terakhir adalah kolom
            *relations_path, final_column_name = path_parts

            # Mulai dari model utama
            current_model = cls

            # Lakukan join berantai untuk setiap relasi di relations_path
            for rel_name in relations_path:
                try:
                    rel = getattr(current_model, rel_name)  # relationship property
                    rel_map = rel.property.mapper  # mapper dari relationship
                except AttributeError:
                    raise ValueError(
                        f"Relasi '{rel_name}' tidak ditemukan di model {current_model.__name__}"
                    )

                # Pakai outerjoin agar baris utama tetap muncul meski relasinya None
                query = query.outerjoin(rel)

                # Pindah current_model ke relasi berikutnya
                current_model = rel_map.class_

            # Terakhir, ambil kolom final
            try:
                final_column = getattr(current_model, final_column_name)
            except AttributeError:
                raise ValueError(
                    f"Kolom '{final_column_name}' tidak ditemukan di model {current_model.__name__}"
                )

            # Terapkan ASC atau DESC
            if descending:
                query = query.order_by(desc(final_column))
            else:
                query = query.order_by(asc(final_column))

        return query
