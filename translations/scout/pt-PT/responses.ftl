# $link (String) - Link to the Scout source code.
get-source = Podes encontrar o meu código fonte aqui { $source }

# $version (Int) - Version of Scout.
# $link (String) - Link to Scout Source Code.
bot-info = Olá, sou o Scout!
    A minha versão atual é { $version }.
    Sou um bot criado para ajudar a  gerenciar servidores de discord, principalmente os relacionados a NationStates.
    A minha principal função atual é lidar com a verificação de nações.
    Eu sou open-source, o meu código fonte pode ser encontrado no Github no seguinte link { $source }
    Agora, onde será que deixei o meu D20...

command-sync = Os Commandos Slash foram sincronizados com o Servidor!

personality-set = "Personality has been set to the requested personality!"

## NSVerify link-roles command

# $role1 (String) - The name of one of the Discord Roles.
# $role2 (String) - The name of the other Discord Role.
link-roles-success-all-roles = Conectado com sucesso, { $role1 } e { $role2 } estão agora registados.

# $role (String) - The name of the Discord Role.
link-roles-success-one = Conectado com sucesso, { $role } está agora registado.

link-roles-no-roles = Eu não conseguirei registar cargos que não forem especificados.
link-roles-no-region = Não foi conectado a uma região. Porfavor conecte para registar cargos.
link-roles-invalid-role = Não consigo registar esse cargo de momento.
link-roles-invalid-meaning = Oh no, I've lost my notes! I can't currently add roles!
link-roles-invalid-meaning = Eu não compreendo oque era suposto estar a fazer.
link-roles-no-override = Infelizmente isso iria subrepor um cargo. Utilize o commando com Sobreposição em Verdadeiro.

## NSVerify link-region command
link-region-with-roles = Esta região foi registrada a este servidor, junto com os cargos!
link-region-only = Esta região foi conectada com este servidor.

link-region-invalid-guild = Não consigo registar esta região de momento.
link-region-invalid-role = Esse cargo não pode ser adicionado de momento, no entanto a região foi registada.
link-region-invalid-meaning = Eu não compreendo oque era suposto estar a fazer.
link-region-no-override = Infelizmente isso iria sobrepor um cardo. Utilize `\connectar_cargos` com sobrepor_cargos em verdadeiro.


## NSVerify unlink-region command
unlink-region-success = A região foi desconectada do se Servidor de Discord.
unlink-region-invalid-region = Essa região não está ligada a esta guild.
unlink-region-invalid-guild = A região ou guild não tem nada associado ou não existe.


## NSVerify verify-nation command

## NSVerify unverify-nation command
unverify-nation-success = I've removed your character sheet from my campaign notes.

no-verified-nations-list = Não existem nações verificadas de momento.