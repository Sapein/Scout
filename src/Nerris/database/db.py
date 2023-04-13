from sqlalchemy import create_engine

def connect(in_memory=True):
    in_memory=True
    if in_memory:
        return create_engine("sqlite+pysqlite:///:memory:")
    return create_engine("sqlite+pysqlite:///nerris_db.sqlite")
