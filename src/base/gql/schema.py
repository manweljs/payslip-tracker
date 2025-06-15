from typing import Any, Generic, List, TypeVar, Optional
import strawberry
from dataclasses import dataclass, asdict
from strawberry.scalars import JSON
import json

T = TypeVar("T")


@strawberry.type
class GQLResponse(Generic[T]):
    success: Optional[bool] = True
    message: Optional[str] = None
    data: Optional[T] = None


@dataclass
class BaseDataModel:
    def model_dump(
        self, exclude: Optional[List[str]] = None, exclude_unset: bool = False
    ) -> dict:
        """
        Mengonversi instance ke dictionary, dengan opsi untuk mengecualikan field tertentu
        dan mengabaikan field yang tidak disetel.

        Args:
            exclude (List[str], optional): Nama-nama field yang akan dikecualikan. Default None.
            exclude_unset (bool, optional): Jika True, hanya menyertakan field yang tidak None.

        Returns:
            dict: Dictionary yang merepresentasikan instance.
        """
        exclude = exclude or []  # Jika exclude None, inisialisasi sebagai list kosong
        data = asdict(self)  # Konversi semua field menjadi dictionary

        if exclude_unset:
            # Hanya sertakan field yang tidak None
            data = {key: value for key, value in data.items() if value is not None}

        # Eksklusi field tertentu
        return {key: value for key, value in data.items() if key not in exclude}


@strawberry.type
class GQLPage(Generic[T]):
    """
    Skema response pagination yang dapat digunakan untuk berbagai tipe data.

    Contoh Struktur Response:
    {
        "items": [...],
        "page": 1,
        "page_size": 10,
        "total": 100,
        "pages": 10
    }
    """

    items: List[T]
    page: int
    page_size: int
    total: int
    pages: int


@strawberry.type
class GQLJSONResponse:
    data: JSON


@strawberry.scalar(name="AnyScalar", description="A scalar that can handle any value")
class AnyScalar:
    @staticmethod
    def serialize(value: Any) -> Any:
        try:
            # Pastikan nilai dapat di-serialize ke JSON

            json.dumps(value)
            return value
        except Exception:
            return str(value)

    @staticmethod
    def parse_value(value: Any) -> Any:
        return value

    @staticmethod
    def parse_value(value: Any) -> Any:
        # Menerima input GraphQL apa adanya
        return value


@strawberry.type
class GraphQLResponse:
    success: bool = True
    message: str = ""
