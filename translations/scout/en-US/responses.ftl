# $link (String) - Link to the Scout source code.
get-source = You can find my source code here! { $source }

# $version (Int) - Version of Scout.
# $link (String) - Link to Scout Source Code.
bot-info = Hi, I'm Scout!
    I am currently Scout Version { $version }
    I am a bot created for The Campfire discord server and the associated NS region Sun's Reach!
    I mostly just help manage nation verification at this time.
    I am Open-Source with my source code available on Github.
    If you wish to read my source code, please go to: { $source }
    Now where did my D20 go...


command-sync = Synced Slash Commands to Server!

personality-set = "Personality has been set to the requested personality!"

## Translation Commands
set_server_language = set_server_language
set_language = set_language

## NSVerify link-roles command

# $role1 (String) - The name of one of the Discord Roles.
# $role2 (String) - The name of the other Discord Role.
link-roles-success-all-roles = A Natural 20, a critical success! I've obtained the mythical +1 roles of { $role1 } and { $role2 }!

# $role (String) - The name of the Discord Role.
link-roles-success-one = Looks like I found the mythical role of { $role }...now to find the other piece.

link-roles-no-roles = I don't know why you're trying to add roles without giving me any...
link-roles-no-region = Looks like you don't have a region associated with this server!
link-roles-invalid-role = Oh no, I rolled a Nat 1! I can't currently add that role!
link-roles-invalid-meaning = Oh no, I've lost my notes! I can't currently add roles!
link-roles-no-override = Unfortunately that would overwrite a role. Use `\link_roles` with overwrite_roles set to True

## NSVerify link-region command
link-region-with-roles = The region has been registered to this server along with the roles!
link-region-only = I've added that world to my maps!

link-region-invalid-guild = Looks like you don't have a region associated with this server!
link-region-invalid-role = Oh no, I rolled a Nat 1! I can't currently add that role!
link-region-invalid-meaning = Oh no, I've lost my notes! I can't currently add roles!
link-region-no-override = Unfortunately that would overwrite a role. Use `\link_roles` with overwrite_roles set to True


## NSVerify unlink-region command
unlink-region-success = I've removed this region from my maps!
unlink-region-invalid-region = I couldn't find that region...
unlink-region-invalid-guild = I couldn't find that region or guild...


## NSVerify verify-nation command

## NSVerify unverify-nation command
unverify-nation-success = I've removed your character sheet from my campaign notes.