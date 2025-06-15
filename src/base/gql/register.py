import inspect
import traceback
import strawberry
import pkgutil
import importlib
from strawberry.exceptions.invalid_union_type import InvalidUnionTypeError
import logging

logger = logging.getLogger(__name__)

# Registry untuk query dan mutation
query_registry = []
mutation_registry = []
subscription_registry = []


def log_source_of_type(type_obj, type_description="Tipe"):
    """Mencoba mendapatkan file dan baris definisi dari sebuah tipe."""
    try:
        source_file = inspect.getsourcefile(type_obj)
        source_lines, starting_line = inspect.getsourcelines(type_obj)
        logger.error(
            "%s %s didefinisikan di: %s, baris %d",
            type_description,
            getattr(type_obj, "__name__", str(type_obj)),
            source_file,
            starting_line,
        )
    except Exception as ex:
        logger.error(
            "Tidak dapat menemukan informasi sumber untuk %s: %s", type_obj, ex
        )


def log_sources_for_union_types(union_def):
    """Mencoba melacak sumber untuk tiap tipe yang terlibat dalam union."""
    if not hasattr(union_def, "types"):
        logger.error("Tidak ada atribut 'types' dalam union_definition.")
        return

    for idx, t in enumerate(union_def.types):
        # Jika tipe merupakan wrapper seperti StrawberryList, ambil tipe dasar
        if hasattr(t, "of_type"):
            base_type = t.of_type
            desc = f"Dasar dari tipe #{idx+1} dalam union"
        else:
            base_type = t
            desc = f"Tipe #{idx+1} dalam union"
        log_source_of_type(base_type, desc)


def log_traceback(tb):
    """Menampilkan traceback dengan file dan nomor baris secara terstruktur."""
    for frame in traceback.extract_tb(tb):
        logger.error(
            "File: %s, line %d, in %s", frame.filename, frame.lineno, frame.name
        )
        if frame.line:
            logger.error("  >> %s", frame.line.strip())


def register_query(query_class):
    """Mendaftarkan query ke registry"""
    query_registry.append(query_class)


def register_mutation(mutation_class):
    """Mendaftarkan mutation ke registry"""
    mutation_registry.append(mutation_class)


def register_subscription(subscription_class):
    """Mendaftarkan subscription ke registry"""
    subscription_registry.append(subscription_class)


def load_all_resolvers(base_package):
    """Muat semua modul dalam package, termasuk subfolder."""
    package = importlib.import_module(base_package)
    package_path = package.__path__

    # Pindai semua modul dalam package dan subfolder
    for module_info in pkgutil.walk_packages(package_path, prefix=f"{base_package}."):
        # logger.info(f"Loading module: {module_info.name}")  # Debug
        importlib.import_module(module_info.name)


def load_app_resolvers(app_root: str):
    """
    Import query.py, mutation.py, subscription.py di seluruh tree `app_root`.
    """
    package = importlib.import_module(app_root)

    # walk_packages menelusuri rekursif
    for modinfo in pkgutil.walk_packages(package.__path__, prefix=f"{app_root}."):
        # Kita hanya butuh modul yang nama akhirnya .query / .mutation / .subscription
        if modinfo.name.endswith((".query", ".mutation", ".subscription")):
            importlib.import_module(modinfo.name)


def build_schema():
    # Muat semua resolver
    # Muat semua resolver dari setiap app di folder `app/`
    load_app_resolvers("app")

    # print(f"Registered queries: {[q.__name__ for q in query_registry]}")
    # print(f"Registered mutations: {[m.__name__ for m in mutation_registry]}")

    if not query_registry and not mutation_registry:
        raise ValueError(
            "Schema registry kosong! Tidak ada query atau mutation yang terdaftar."
        )

    # Gabungkan semua query dari registry
    if query_registry:
        Query = type("Query", tuple(query_registry), {})
        Query = strawberry.type(Query)
    else:
        Query = None

    # Gabungkan semua mutation dari registry
    if mutation_registry:
        Mutation = type("Mutation", tuple(mutation_registry), {})
        Mutation = strawberry.type(Mutation)
    else:
        Mutation = None

    # Gabungkan semua subscription dari registry
    if subscription_registry:
        Subscription = type("Subscription", tuple(subscription_registry), {})
        Subscription = strawberry.type(Subscription)
    else:
        Subscription = None

    # --------------------------------------------------------------------------
    # Create the schema
    # --------------------------------------------------------------------------

    try:
        schema = strawberry.Schema(
            query=Query, mutation=Mutation, subscription=Subscription
        )
        return schema
    except InvalidUnionTypeError as e:
        logger.error("Terjadi kesalahan pada definisi GraphQL Union.")
        logger.error("Pesan: %s", e.message)

        union_def = e.union_definition
        union_name = getattr(union_def, "name", str(e.union_name))
        logger.error("Nama Union: %s", union_name)
        logger.error("Tipe yang tidak valid: %s", e.invalid_type)

        if hasattr(union_def, "types"):
            logger.error("Jenis-jenis dalam union:")
            for t in union_def.types:
                type_name = getattr(t, "name", str(t))
                logger.error(" - %s", type_name)
        else:
            logger.error("Definisi Union: %s", union_def)

        # Log sumber untuk tiap tipe dalam union
        logger.error("Melacak sumber untuk tiap tipe dalam union:")
        log_sources_for_union_types(union_def)

        logger.error("Detail Traceback:")
        log_traceback(e.__traceback__)
        raise

    except Exception as e:
        logger.error("Exception tidak terduga: %s", e)
        logger.error("Detail Traceback:")
        log_traceback(e.__traceback__)
        raise
