class InvalidAssociation(Exception):
    pass


class AssociationRegistered(Exception):
    pass


class InvalidGuild(Exception):
    pass


class InvalidRole(Exception):
    pass


class RoleOverwrite(Exception):
    pass


class NoRoles(Exception):
    pass


class NoGuilds(Exception):
    pass


class NoAssociations(Exception):
    pass


class NoNation(Exception):
    pass


# noinspection PyPep8Naming
class InvalidCode_NSVerify(Exception):
    pass


# noinspection PyPep8Naming
class NoCode_NSVerify(Exception):
    pass
