from enum import Enum, unique

#XXX: This is deprecated and is in the process of being removed.

class RoleTypes(Enum):
    RESIDENT = "resident".casefold()
    VERIFIED = "verified".casefold()
