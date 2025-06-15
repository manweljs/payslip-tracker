from sqlmodel import SQLModel
from typing import List, Optional


class Serializer:
    @staticmethod
    def serialize(instance: SQLModel, relations: Optional[List[str]] = None) -> dict:
        """
        Serializes an instance of the model, including nested relations.
        Supports both '.' and '__' as separators for nested relations.
        """
        # Mulai dengan data utama instance
        serialized_data = instance.model_dump()

        if relations:
            for relation in relations:
                # Tentukan separator yang digunakan
                if "__" in relation:
                    split_relations = relation.split("__")
                elif "." in relation:
                    split_relations = relation.split(".")
                else:
                    split_relations = [relation]

                current_data = serialized_data
                current_instance = instance

                for i, part in enumerate(split_relations):
                    # Coba ambil atribut terkait
                    related_instance = getattr(current_instance, part, None)
                    if related_instance is None:
                        break  # Tidak ada data terkait

                    # Jika ini adalah bagian terakhir dari relasi
                    if i == len(split_relations) - 1:
                        if isinstance(related_instance, list):
                            # Jika relasi adalah list, serialisasikan setiap item
                            current_data[part] = [
                                Serializer.serialize(item) for item in related_instance
                            ]
                        else:
                            # Jika relasi adalah satu objek, serialisasikan langsung
                            current_data[part] = Serializer.serialize(related_instance)
                    else:
                        # Jika ini adalah relasi nested, pastikan dictionary ada
                        if part not in current_data:
                            current_data[part] = {}
                        current_data = current_data[part]
                        current_instance = related_instance

        return serialized_data
