from enum import Enum, unique

class RoleTypes(Enum):
    RESIDENT = "resident".casefold()
    VERIFIED = "verified".casefold()
