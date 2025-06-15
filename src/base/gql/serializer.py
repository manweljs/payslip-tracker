import dataclasses
import sys
import logging
from typing import (
    Literal,
    Type,
    TypeVar,
    get_type_hints,
    Union,
    List,
    Optional,
    Set,
    get_origin,
    get_args,
    overload,
)
import typing
from sqlalchemy import inspect
from sqlalchemy.orm import attributes

logger = logging.getLogger(__name__)


async def serialize_instance(
    cls,
    instance: object,
    visited: Optional[Set[int]] = None,
    instance_cache: Optional[dict] = None,
    path: str = "",
):
    """
    Fungsi helper serialization:
    - Mengembalikan instance 'cls(**filtered_data)' agar Strawberry bisa memanggil .id, .avatar, dsb.
    - Mencegah infinite loop memakai 'visited' + 'instance_cache'.
      - 'visited' mencegah kita melakukan proses serialize yang sama berulang kali
      - 'instance_cache' menyimpan object schema yang sudah dibuat,
        agar kita tidak buat instance baru untuk object yang sama.

    :param cls: Kelas schema Strawberry/Python yang akan dibangun, misalnya VacancySchema
    :param instance: Object SQLAlchemy model atau dictionary
    :param visited: Set berisi id(object) yang sudah pernah diserialize
    :param instance_cache: Dict { id(object_asli): instance_schema } yang sudah dibentuk
    :param path: String untuk debug path relasi
    :return: Instance dari 'cls' (bisa None jika loop)
    """
    logger.debug(f"[serialize_instance] start -> path={path}, instance={instance}")

    # 1) Handle None
    if instance is None:
        logger.debug(f"[serialize_instance] instance is None -> path={path}")
        return None

    # 2) Persiapkan visited & instance_cache
    if visited is None:
        visited = set()
    if instance_cache is None:
        instance_cache = {}

    original_id = id(instance)
    # Jika object ini sudah pernah divisit => return instance yg sudah di-cache, atau None
    if original_id in visited:
        # Artinya, kita sudah pernah serialize object ini
        logger.debug(
            f"[serialize_instance] skip visited -> path={path}, id={original_id}"
        )
        return instance_cache.get(original_id, None)

    visited.add(original_id)

    # 3) Dump data dasar
    if hasattr(instance, "model_dump"):
        data = instance.model_dump()  # SQLModel, Pydantic, dsb.
        logger.debug(f"[serialize_instance] model_dump -> path={path}, data={data}")
    elif isinstance(instance, dict):
        data = instance
        logger.debug(
            f"[serialize_instance] instance is dict -> path={path}, data={data}"
        )
    else:
        raise ValueError(
            f"[serialize_instance] {type(instance).__name__} tidak punya 'model_dump'"
        )

    # 4) Dapatkan type hints
    mod = sys.modules[cls.__module__]
    resolved_type_hints = get_type_hints(cls, globalns=mod.__dict__, localns=None)

    # 5) Ambil relationships (SQLAlchemy)
    if not isinstance(instance, dict):
        sa_relationships = inspect(instance.__class__).relationships.keys()
        sa_state = attributes.instance_state(instance)
    else:
        sa_relationships = []
        sa_state = None

    logger.debug(f"[serialize_instance] path={path}, relationships={sa_relationships}")

    # 6) Proses setiap relationship
    for rel_name in sa_relationships:
        child_path = f"{path}.{rel_name}" if path else rel_name

        exists_in_state = False
        if sa_state is not None:
            exists_in_state = rel_name in sa_state.dict

        current_value = data.get(rel_name)
        logger.debug(
            f"[serialize_instance] path={child_path}, rel={rel_name}, "
            f"exists_in_state={exists_in_state}, current_value={current_value!r}"
        )

        # Jika relasi tidak ada di state.dict dan belum ada di data => set None
        if not exists_in_state and current_value is None:
            data[rel_name] = None
            continue

        # Jika data sudah terisi dan bukan None => skip
        if rel_name in data and data[rel_name] is not None:
            continue

        # Ambil object relasinya (kalau instance bukan dict)
        rel_value = getattr(instance, rel_name, None) if sa_state else None

        if not rel_value:
            data[rel_name] = None
            continue

        # Cek type hint
        rel_type = resolved_type_hints.get(rel_name, None)
        if not rel_type:
            # Tidak ada hint => raw value saja
            data[rel_name] = rel_value
            continue

        # Cek apakah union / list / single object
        origin = get_origin(rel_type)
        args = get_args(rel_type)

        # Jika Union[SomeType, None], ambil SomeType
        if origin is Union and type(None) in args:
            real_type = next(a for a in args if a is not type(None))
            origin = get_origin(real_type)
            args = get_args(real_type)
        else:
            real_type = rel_type

        # 6a) List
        if origin in (list, List):
            elem_type = args[0] if args else None
            if elem_type and hasattr(elem_type, "_serialize"):
                new_list = []
                for idx, item in enumerate(rel_value):
                    item_path = f"{child_path}[{idx}]"
                    sub_inst = await elem_type._serialize(
                        item, visited, instance_cache, item_path
                    )
                    new_list.append(sub_inst)
                data[rel_name] = new_list
            else:
                data[rel_name] = rel_value

        # 6b) Single object
        elif hasattr(rel_value, "model_dump") or isinstance(rel_value, dict):
            # Panggil _serialize rel_type
            if hasattr(real_type, "_serialize"):
                sub_obj = await real_type._serialize(
                    rel_value, visited, instance_cache, child_path
                )
                data[rel_name] = sub_obj
            else:
                data[rel_name] = rel_value
        else:
            data[rel_name] = rel_value

    # 7) Filter fields agar sesuai schema
    schema_fields = set(resolved_type_hints.keys())
    filtered_data = {k: v for k, v in data.items() if k in schema_fields}

    # 8) Buat instance schema -> 'cls(**filtered_data)'
    #    Lalu simpan di instance_cache
    schema_instance = cls(**filtered_data)

    # Pastikan validator dijalankan dengan memanggil __post_init__ secara eksplisit
    # if hasattr(schema_instance, "__post_init__"):
    #     schema_instance.__post_init__()

    instance_cache[original_id] = schema_instance

    logger.debug(
        f"[serialize_instance] done -> path={path}, instance={schema_instance}"
    )
    return schema_instance


# ======================================================
# TAHAP 1: SERIALISASI KE DICTIONARY (Tanpa Membuat Schema)
# ======================================================
async def serialize_to_dict(
    cls,
    instance: object,
    visited: Optional[Set[int]] = None,
    path: str = "",
) -> Optional[dict]:
    """
    Tahap 1: Rekursif mengekstrak data instance (SQLAlchemy model / dict)
    menjadi dictionary, tanpa membuat instance schema.
    Menghindari infinite loop dengan 'visited' (berdasarkan id(instance)).
    """
    logger.debug(f"[serialize_to_dict] start -> path={path}, instance={instance}")
    if instance is None:
        logger.debug(f"[serialize_to_dict] instance is None -> path={path}")
        return None

    if visited is None:
        visited = set()

    obj_id = id(instance)
    if obj_id in visited:
        logger.debug(f"[serialize_to_dict] skip visited -> path={path}, id={obj_id}")
        return None

    visited.add(obj_id)

    # 1) Buat dictionary dasar (dari model_dump / dict)
    if hasattr(instance, "model_dump"):
        data = instance.model_dump()
        logger.debug(f"[serialize_to_dict] model_dump -> path={path}, data={data}")
    elif isinstance(instance, dict):
        data = dict(instance)  # copy agar aman
        logger.debug(
            f"[serialize_to_dict] instance is dict -> path={path}, data={data}"
        )
    else:
        raise ValueError(f"{type(instance).__name__} tidak punya 'model_dump'")

    # 2) Ambil type hints di 'cls' untuk filter & menelusuri relasi
    mod = sys.modules[cls.__module__]
    resolved_type_hints = get_type_hints(cls, globalns=mod.__dict__)

    # 3) SQLAlchemy relationship
    sa_relationships = []
    sa_state = None
    if not isinstance(instance, dict):
        sa_relationships = inspect(instance.__class__).relationships.keys()
        sa_state = attributes.instance_state(instance)

    for rel_name in sa_relationships:
        child_path = f"{path}.{rel_name}" if path else rel_name

        # Periksa apakah rel_name ada di state
        exists_in_state = (rel_name in sa_state.dict) if sa_state else False
        current_value = data.get(rel_name)

        if not exists_in_state and current_value is None:
            data[rel_name] = None
            continue

        # Kalau dari model_dump() sudah ada isinya, skip
        if rel_name in data and data[rel_name] is not None:
            continue

        # Ambil object relasinya
        rel_value = getattr(instance, rel_name, None) if sa_state else None
        if not rel_value:
            data[rel_name] = None
            continue

        # Cek type hint
        rel_type = resolved_type_hints.get(rel_name, None)
        if not rel_type:
            # Tanpa hint => masukkan raw
            data[rel_name] = rel_value
            continue

        origin = get_origin(rel_type)
        args = get_args(rel_type)

        # Jika Union[Something, None], ambil Something
        if origin is Union and type(None) in args:
            real_type = next(a for a in args if a is not type(None))
            origin = get_origin(real_type)
            args = get_args(real_type)
        else:
            real_type = rel_type

        # Rekursif ke sub-item
        if origin in [list, List]:
            # list of sub-object
            new_list = []
            for idx, item in enumerate(rel_value):
                item_path = f"{child_path}[{idx}]"
                sub_data = await serialize_to_dict(real_type, item, visited, item_path)
                new_list.append(sub_data)
            data[rel_name] = new_list
        elif hasattr(rel_value, "model_dump") or isinstance(rel_value, dict):
            sub_dict = await serialize_to_dict(
                real_type, rel_value, visited, child_path
            )
            data[rel_name] = sub_dict
        else:
            data[rel_name] = rel_value

    # 4) Filter fields berdasarkan schema
    # 4) Filter fields berdasarkan schema
    schema_fields = set(
        field for field, hint in resolved_type_hints.items() if not hasattr(cls, field)
    )
    filtered_data = {k: v for k, v in data.items() if k in schema_fields}

    logger.debug(f"[serialize_to_dict] done -> path={path}, dict={filtered_data}")
    return filtered_data


# ======================================================
# TAHAP 2: Membangun Instance Schema Dari Dictionary
# ======================================================
def dict_to_instance(cls, data: dict) -> object:
    """
    Tahap 2: Ubah dictionary (hasil tahap 1) menjadi instance 'cls(...)'.
    Jika ada nested dictionary yang juga perlu diubah menjadi sub-instance,
    kita bisa melakukannya secara rekursif.
    """
    if data is None:
        return None

    logger.debug(f"[dict_to_instance] building -> cls={cls.__name__}, data={data}")

    # Dapatkan type hints
    mod = sys.modules[cls.__module__]
    resolved_type_hints = get_type_hints(cls, globalns=mod.__dict__)

    # Siapkan dictionary final
    final_data = {}

    for field_name, field_type in resolved_type_hints.items():
        value = data.get(field_name)
        if value is None:
            final_data[field_name] = None
            continue

        origin = get_origin(field_type)
        args = get_args(field_type)

        # Apakah Union?
        if origin is Union and type(None) in args:
            # Contoh: Optional[Something]
            real_type = next(a for a in args if a is not type(None))
            origin = get_origin(real_type)
            args = get_args(real_type)
        else:
            real_type = field_type

        # Jika list
        if origin in [list, List]:
            elem_type = args[0] if args else None
            if elem_type and hasattr(elem_type, "_serialize"):
                # Berarti sub-elem adalah schema
                new_list = []
                for item in value:
                    if isinstance(item, dict):
                        new_list.append(dict_to_instance(elem_type, item))
                    else:
                        new_list.append(item)
                final_data[field_name] = new_list
            else:
                final_data[field_name] = value

        # Jika object (nested)
        elif isinstance(value, dict) and hasattr(real_type, "_serialize"):
            # Rekursif
            nested_obj = dict_to_instance(real_type, value)
            final_data[field_name] = nested_obj
        else:
            final_data[field_name] = value

    # Bangun instance schema
    valid_fields = set(get_type_hints(cls).keys())
    final_data = {k: v for k, v in final_data.items() if k in valid_fields}
    instance_obj = cls(**final_data)
    logger.debug(f"[dict_to_instance] done -> instance={instance_obj}")
    return instance_obj


# ======================================================
# Membangun Instance Dataclass Dari Dictionary
# ======================================================


def _dict_to_dataclass_instance(cls, data, depth=0):

    try:
        indent = '  ' * depth

        # Jika data None
        if data is None:
            logger.debug(f"{indent}Data is None, returning None for {cls.__name__}")
            return None

        # Jika data adalah list, kita kembalikan list juga
        if isinstance(data, list):
            logger.debug(
                f"{indent}Data untuk {cls.__name__} adalah list, memproses setiap item."
            )
            # Misal: kita ingin tiap item diperlakukan seperti biasa,
            # dengan memanggil dict_to_dataclass_instance jika item tersebut dict
            return [
                (
                    dict_to_dataclass_instance(cls, item, depth + 1)
                    if isinstance(item, dict)
                    else item
                )
                for item in data
            ]

        # Jika data bukan dict (dan bukan list), kita kembalikan apa adanya
        if not isinstance(data, dict):
            logger.debug(
                f"{indent}Data untuk {cls.__name__} bukan dict, kembalikan apa adanya: {data}"
            )
            return data

        # Jika class yang dituju bukan dataclass, kembalikan data apa adanya
        if not dataclasses.is_dataclass(cls):
            logger.debug(
                f"{indent}{cls.__name__} is not a dataclass. Returning data as is."
            )
            return data

        # Resolve forward references
        resolved_types = typing.get_type_hints(cls)

        # Pada titik ini, kita tahu data adalah dict,
        # jadi aman memanggil data.keys().
        logger.debug(
            f"{indent}Converting to {cls.__name__} with keys: {list(data.keys())}"
        )

        field_definitions = dataclasses.fields(cls)
        kwargs = {}

        for field in field_definitions:
            field_name = field.name
            field_type = resolved_types.get(field_name, field.type)
            field_value = data.get(field_name)
            origin = get_origin(field_type)

            logger.debug(
                f"{indent}Processing field '{field_name}' of type {field_type}"
            )

            if field_value is None:
                logger.debug(
                    f"{indent}  Value for field '{field_name}' not found or None."
                )
                kwargs[field_name] = None
                continue

            # Unwrap Optional[...] jika diperlukan
            if origin is Union:
                args = get_args(field_type)
                non_none_args = [arg for arg in args if arg is not type(None)]
                if len(non_none_args) == 1:
                    field_type = non_none_args[0]
                    origin = get_origin(field_type)

            # Cek dan resolve LazyType jika ada
            if hasattr(field_type, 'type_name') and hasattr(field_type, 'module'):
                try:
                    module = __import__(
                        field_type.module, fromlist=[field_type.type_name]
                    )
                    resolved = getattr(module, field_type.type_name)
                    logger.debug(
                        f"{indent}  Resolved LazyType untuk '{field_name}' menjadi {resolved}"
                    )
                    field_type = resolved
                    origin = get_origin(field_type)
                except Exception as e:
                    logger.debug(
                        f"{indent}  Gagal resolve LazyType untuk '{field_name}': {e}"
                    )
                    kwargs[field_name] = field_value
                    continue

            # Tangani tipe List[...]
            if origin in {list, List}:
                inner_type = get_args(field_type)[0]
                logger.debug(
                    f"{indent}  Field '{field_name}' adalah List[{inner_type}]"
                )
                if dataclasses.is_dataclass(inner_type):
                    kwargs[field_name] = [
                        (
                            dict_to_dataclass_instance(inner_type, item, depth + 2)
                            if isinstance(item, dict)
                            else item
                        )
                        for item in field_value
                    ]
                else:
                    # Jika inner_type bukan dataclass, kembalikan list apa adanya
                    kwargs[field_name] = field_value

            # Tangani nested dataclass
            elif dataclasses.is_dataclass(field_type) and isinstance(field_value, dict):
                logger.debug(
                    f"{indent}  Field '{field_name}' adalah nested dataclass {field_type.__name__}"
                )
                kwargs[field_name] = dict_to_dataclass_instance(
                    field_type, field_value, depth + 1
                )

            else:
                logger.debug(
                    f"{indent}  Assigning field '{field_name}' dengan nilai: {field_value}"
                )
                kwargs[field_name] = field_value

        instance = cls(**kwargs)
        logger.debug(f"{indent}Created instance of {cls.__name__}: {instance}")
        return instance
    except Exception as e:
        raise Exception(f"Error while converting {cls.__name__}: {e}")


T = TypeVar("T")


@overload
def dict_to_dataclass_instance(
    cls: Type[T], data: dict, depth: int = ..., many: Literal[False] = ...
) -> T: ...


@overload
def dict_to_dataclass_instance(
    cls: Type[T], data: List[dict], depth: int = ..., many: Literal[True] = ...
) -> List[T]: ...


def dict_to_dataclass_instance(
    cls: Type[T],
    data: Union[dict, List[dict]],
    depth: int = 0,
    many: Optional[bool] = False,
) -> Union[T, List[T]]:
    """
    Build a dataclass instance from a dictionary.
    This function will process each field in the dataclass,
    and build a dataclass instance based on the data provided.

    :param cls: Dataclass that will be built
    :type cls: Type
    :param data: Dictionary containing data for the dataclass
    :type data: dict
    :return: Dataclass instance that has been built
    :rtype: cls
    :raises Exception: If an error occurs while converting the data

    Example:
    >>> @dataclasses.dataclass
    ... class Person:
    ...     name: str
    ...     age: int
    ...     address: str
    ...
    >>> data = {'name': 'Alice', 'age': 30, 'address': '123 Main St'}
    >>> person = dict_to_dataclass_instance(Person, data)
    >>> print(person)
    Person(name='Alice', age=30, address='123 Main St')
    """
    if many and isinstance(data, list):
        return [_dict_to_dataclass_instance(cls, item, depth) for item in data]
    return _dict_to_dataclass_instance(cls, data, depth)
