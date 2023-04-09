from sqlalchemy import create_engine

def connect(in_memory=True):
    if in_memory:
        return create_engine("sqlite+pysqlite:///:memory:")

    raise NotImplementedError("Only in_memory is supported!")