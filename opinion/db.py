import os


class DatabaseUnavailable(RuntimeError):
    pass


def get_db():
    try:
        from grlibs.mdb import db3
        return db3.opinion
    except Exception as grlibs_exc:
        uri = os.getenv("MONGO_URI")
        if not uri:
            raise DatabaseUnavailable("Cannot import grlibs.mdb.db3 and MONGO_URI is not set") from grlibs_exc
        try:
            from pymongo import MongoClient
        except Exception as pymongo_exc:
            raise DatabaseUnavailable("MONGO_URI is set, but pymongo is not installed") from pymongo_exc
        return MongoClient(uri)[os.getenv("MONGO_DB", "opinion")]


def object_id(value):
    try:
        from bson import ObjectId
    except Exception:
        return value
    try:
        return ObjectId(value)
    except Exception:
        return value


def ensure_indexes(db):
    db.plans.create_index("enabled")
    db.items.create_index("unique_key", unique=True)
    db.items.create_index("created_at")
    db.items.create_index("related")
    db.runs.create_index("started_at")
