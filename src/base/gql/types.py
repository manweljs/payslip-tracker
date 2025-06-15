# graphql_app/types.py
import asyncio
import json
import strawberry
from strawberry.types import Info as StrawberryInfo

from .serializer import serialize_instance
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Set,
    TypeVar,
    Optional,
)
from strawberry import type as strawberry_type

if TYPE_CHECKING:
    from .app import ContextWrapper


class Info(StrawberryInfo["ContextWrapper", None]):  # Inherit dari Info Strawberry
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def db(self):
        """Shortcut for accessing the database session from context."""
        return self.context.db

    @property
    async def user(self):
        """Shortcut for accessing user from context."""
        return await self.context.user

    @property
    async def partner(self):
        """Shortcut for accessing partner from context."""
        return await self.context.partner


ModelType = TypeVar("ModelType")
GraphQLType = TypeVar("GraphQLType")


class ValidatorMeta(type):
    def __init__(cls, name, bases, namespace):
        cls._validators = {}

        # Cari semua validator yang didekorasi dengan @validator
        for attr_name, attr_value in namespace.items():
            if callable(attr_value) and hasattr(attr_value, "_validator_fields"):
                for field in attr_value._validator_fields:
                    cls._validators.setdefault(field, []).append(attr_value)

        # Dekorasi class dengan @strawberry.type secara otomatis
        strawberry_type(cls)

        super().__init__(name, bases, namespace)


def validator(*fields: str):
    """
    Dekorator untuk menandai fungsi sebagai validator untuk field tertentu.

    Fungsi ini memungkinkan Anda menentukan logika validasi atau manipulasi data
    pada level schema. Validator diterapkan ke field-field tertentu yang disebutkan
    dalam parameter `fields`.

    Validator akan dipanggil secara otomatis setelah instance schema dibuat (melalui `__post_init__`),
    dengan parameter `self` (schema instance) dan `value` (nilai field yang sedang diproses).

    Parameters
    ----------
    *fields : str
        Nama field yang harus diproses oleh validator ini. Anda dapat memberikan
        lebih dari satu nama field sebagai parameter.

    Returns
    -------
    Callable
        Dekorator yang menambahkan field ke daftar validasi dan mengikatnya ke fungsi yang didekorasi.

    Usage
    -----
    @validator("google_address")
    def validate_google_address(self, value):
        if isinstance(value, str):
            # Contoh parsing JSON menjadi objek Python
            parsed_data = json.loads(value)
            return GoogleAddress(**parsed_data)
        return value

    @validator("another_field", "yet_another_field")
    def validate_multiple_fields(self, value):
        # Validasi yang sama diterapkan ke beberapa field
        if value is None:
            return "Default Value"
        return value

    Notes
    -----
    - Dekorator ini hanya menandai fungsi sebagai validator untuk field yang ditentukan.
    - Logika validasi harus ditentukan di dalam fungsi yang didekorasi.
    - Validator diterapkan setelah inisialisasi schema melalui `__post_init__`.
    """

    def decorator(func):
        func._validator_fields = fields
        return func

    return decorator


class BaseGraphQLSchema(metaclass=ValidatorMeta):
    """
    BaseGraphQLSchema is a mixin class designed to automatically reflect fields from
    the `__dataclass_fields__` attribute to an instance and handle custom resolvers.
    """

    def __post_init__(self):
        """
        Otomatis memanggil validator untuk setiap field setelah inisialisasi.
        Perbaikan:
         - Tambahkan pengecekan `hasattr(self, field)` agar tidak error
           bila Strawberry belum menyiapkan field forward reference.
        """
        # Jalankan validator hanya pada field yang benar-benar ada
        for field, funcs in self.__class__._validators.items():
            # Pastikan field ini benar-benar ada di instance
            if hasattr(self, field):
                current_value = getattr(self, field, None)
                for func in funcs:
                    validated_value = func(self, current_value)
                    setattr(self, field, validated_value)

    @classmethod
    async def _serialize(
        cls,
        instance,
        visited: Optional[Set[int]] = None,
        instance_cache: Optional[Dict[int, object]] = None,
        path: str = "",
    ):
        """
        Meneruskan call ke serialize_instance yang akan:
          - Menangani visited agar tidak infinite loop
          - Menyimpan instance hasil pembuatan ke instance_cache
          - Return cls(**filtered_data)
        """
        return await serialize_instance(cls, instance, visited, instance_cache, path)

    # @classmethod
    # @timer
    # async def serialize(cls, instances, many: bool = False):
    #     """
    #     Serialize instance(s) into GraphQL schema.

    #     Args:
    #         instances (Union[ModelType, List[ModelType]]): Instance(s) to serialize.
    #         many (bool, optional): Serialize as list. Defaults to `False`.

    #     Returns:
    #         results (Union[GraphQLType, List[GraphQLType]]): Serialized instance(s).
    #     """
    #     visited = set()
    #     instance_cache = {}

    #     if many and isinstance(instances, list):
    #         results = []
    #         for idx, item in enumerate(instances):
    #             path = f"{cls.__name__}[{idx}]"
    #             schema_inst = await cls._serialize(item, visited, instance_cache, path)
    #             results.append(schema_inst)
    #     else:
    #         path = cls.__name__
    #         results = await cls._serialize(instances, visited, instance_cache, path)

    #     return results

    @classmethod
    async def serialize(cls, instances, many: bool = False):
        """
        Serialize instance(s) into GraphQL schema.

        Parameters
        ----------
        instances : Union[ModelType, List[ModelType]]
            Instance(s) to serialize.
        many : bool, optional
            Serialize as list. Defaults to `False`.

        Returns
        -------
        results : Union[GraphQLType, List[GraphQLType]]
            Serialized instance(s).
        """
        visited = set()
        instance_cache = {}

        if many and isinstance(instances, list):
            tasks = []
            for idx, item in enumerate(instances):
                path = f"{cls.__name__}[{idx}]"
                # Kumpulkan tugas asinkron
                tasks.append(cls._serialize(item, visited, instance_cache, path))

            # Jalankan semua tugas secara paralel
            results = await asyncio.gather(*tasks)
        else:
            path = cls.__name__
            results = await cls._serialize(instances, visited, instance_cache, path)

        return results


# ----------------------------------------------------------------------
# Base Input GraphQL
# ----------------------------------------------------------------------


class InputMeta(type):
    def __new__(cls, name, bases, dct):
        # Buat class baru
        new_class = super().__new__(cls, name, bases, dct)
        # Dekorasi otomatis sebagai input
        return strawberry.input(new_class)


class BaseGraphQLInput(metaclass=InputMeta):
    def model_dump(
        self, exclude: Optional[List[str]] = None, exclude_unset: bool = False
    ) -> dict:
        """
        Serialisasi instance ke dictionary, dengan opsi untuk mengecualikan field tertentu
        dan hanya menyertakan field yang tidak None.
        """
        try:
            exclude = exclude or []
            data = vars(
                self
            )  # Mengambil semua atribut dari instance sebagai dictionary

            if exclude_unset:
                # Hanya sertakan field yang tidak None
                data = {key: value for key, value in data.items() if value is not None}

            # Eksklusi field tertentu
            return {key: value for key, value in data.items() if key not in exclude}
        except Exception as e:
            raise ValueError(f"Error serializing instance: {e}")

    def model_dump_json(
        self, exclude: Optional[List[str]] = None, exclude_unset: bool = False, **kwargs
    ) -> str:
        """
        Serializes the instance to a JSON string, with options to exclude certain fields
        and only include fields that are not None.

        Parameters:
            exclude (Optional[List[str]]): List of fields to exclude.
            exclude_unset (bool): If True, only include fields that are not None.
            **kwargs: Additional parameters for json.dumps (e.g., indent=4).

        Returns:
            str: The JSON string representation of the instance.
        """
        try:
            data = self.model_dump(exclude=exclude, exclude_unset=exclude_unset)
            return json.dumps(
                data,
                default=lambda o: (
                    o.model_dump() if isinstance(o, BaseGraphQLInput) else str(o)
                ),
                **kwargs,
            )
        except Exception as e:
            raise ValueError(f"Error serializing instance to JSON: {e}")
