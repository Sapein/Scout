class DBError(Exception):
    """
    This represents all Nerris-Specific Database errors that can occur.
    """
    pass


class NotFound(DBError, ValueError):
    """
    Represents any time we can't find an item in the DB.
    """
    pass

class UserNotFound(NotFound):
    """
    This is raised when a user can not be found
    """
    pass


class RegionNotFound(NotFound):
    """
    This is raised when a region is not found within the Database.
    """
    pass


class RegionNameNotFound(RegionNotFound):
    """
    This is raised when a region is not found by a name.
    """
    pass


class RegionIdNotFound(RegionNotFound):
    """
    This is raised specifically if a region can not be found by ID.
    """
    pass


class NationNotFound(NotFound):
    """
    This is raised in the event that a nation can not be found.
    """
    pass


class RoleNotFound(NotFound):
    """
    This is raised when a role is not found.
    """
    pass


class GuildNotFound(NotFound):
    """
    This is raised if a guild is not found in the DB
    """
    pass
