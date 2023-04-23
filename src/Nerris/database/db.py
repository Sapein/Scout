"""
This is a more 'high level' of sorts DB interface.
"""

from typing import Optional, cast
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

def db_connect(dialect: str, driver: Optional[str], table: Optional[str], login: dict[str, Optional[str]], connect: dict[str, Optional[str | int]]):
    """
    Handles database conenction stuff
    """
    driver_name = dialect
    if driver:
        driver_name = "{}+{}".format(driver_name, driver)

    uri = URL.create(driver_name,
                     username=login.get('user', None),
                     password=login.get('password', None),
                     host=cast(Optional[str], connect.get('host', None)),
                     port=cast(Optional[int], connect.get('port', None)),
                     database=table)
    return create_engine(uri)
