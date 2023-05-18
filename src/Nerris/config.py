"""
Handles configuration for Nerris
"""

import tomllib
import os
from typing import Optional

import dotenv


def default_values() -> dict[str, str]:
    """
    Returns the default values.
    """
    return {
        "CONFIG_FILE": "nerris.toml",
        "PREFIXES": ".:,:I cast:I roll for",
        "PREFIXLESS_DMS": "False",
        "PING_PREFIX": "True",
        "DB_DIALECT": "sqlite",
        "REGION": "",
    }


def envar_setup() -> dict[str, Optional[str]]:
    """
    Handles the immediate setup of Environment Variables
    """
    return {
        **default_values(),
        **dotenv.dotenv_values(".env"),
        **os.environ
    }


def toml_setup(path: str):
    """
    Handles the parsing of the toml file.
    """
    try:
        with open(path, 'rb') as file:
            return tomllib.load(file)
    except (tomllib.TOMLDecodeError, FileNotFoundError):
        return {}


def toml_flatten(toml_config):
    """
    Flattens TOML to the env_var format.
    """

    def check_str(value: str, name: str = "") -> str:
        if value.strip():
            return value
        raise ValueError("You MUST pass a value for {}".format(name))

    def str_to_opt_int(value: str) -> Optional[int]:
        try:
            return int(value)
        except ValueError:
            return None

    def str_to_opt_str(value: str) -> Optional[str]:
        match value.strip():
            case '':
                return None
            case _:
                return value

    return {
        "PREFIXES": toml_config['bot']['commands']['PREFIXES'],
        "PREFIXLESS_DMS": toml_config['bot']['commands']['ALLOW_PREFIXLESS_IN_DMS'],
        "PING_PREFIX": toml_config['bot']['commands']['ALLOW_PING_AS_PREFIX'],
        "DISCORD_API_KEY": toml_config['bot']['api']['discord']['API_KEY'],
        "NATION": check_str(toml_config['bot']['api']['n']['NATION'], 'api.n.NATION'),
        "CONTACT_INFO": check_str(toml_config['bot']['api']['n']['CONTACT_INFO'], "api.n.CONTACT_INFO"),
        "REGION": str_to_opt_str(toml_config['bot']['api']['n']['REGION']),
        "DB_DIALECT": check_str(toml_config['bot']['database']['sql']['DIALECT'], "database.sql.DIALECT"),
        "DB_DRIVER": str_to_opt_str(toml_config['bot']['database']['sql']['DRIVER']),
        "DB_TABLE": str_to_opt_str(toml_config['bot']['database']['sql']['TABLE']),
        "DB_LOGIN": toml_config['bot']['database']['sql']['LOGIN'],
        "DB_CONN": toml_config['bot']['database']['sql']['CONNECTION']
    }


def pythonize_env(env_config):
    """
    Turns the environment variable values into actual python types.
    """

    def check_str(value: str, name: str = "") -> str:
        if value.strip():
            return value
        raise ValueError("You MUST pass a value for {}".format(name))

    def str_to_bool(val: str) -> bool:
        match val.casefold():
            case "true":
                return True
            case _:
                return False

    def str_to_opt_str(value: str) -> Optional[str]:
        match value.strip():
            case '':
                return None
            case _:
                return value

    for (key, val) in env_config.items():
        match key:
            case "PREFIXES":
                env_config[key] = [k for k in val.split(":") if k]
            case "PREFIXLESS_DMS" | "PING_PREFIX":
                env_config[key] = str_to_bool(val)
            case "REGION" | "DB_DRIVER" | "TABLE":
                env_config[key] = str_to_opt_str(val)
            case "DB_LOGIN":
                env_config[key] = {'user': val.split(":")[0], 'password': val.split(":")[1]}
            case "DB_CONN":
                try:
                    env_config[key] = {'host': val.split(":")[0], 'port': int(val.split(":")[1])}
                except (IndexError, ValueError):
                    env_config[key] = {'host': val.split(":")[0], 'port': None}

    if "NATION" not in env_config or not env_config["NATION"].strip():
        raise ValueError("You MUST pass in a Nation!")

    if "CONTACT_INFO" not in env_config or not env_config["CONTACT_INFO"].strip():
        raise ValueError("You MUST pass in contact information!")

    if "DB_DIALECT" not in env_config or not env_config["DB_DIALECT"].strip():
        raise ValueError("You MUST provide a dialect. Use 'sqlite' if you don't know what this means.")

    if "DB_LOGIN" not in env_config:
        env_config["DB_LOGIN"] = {'user': env_config.get("DB_USER", None), 'password': env_config.get("DB_PASS", None)}

    if "DB_CONN" not in env_config:
        try:
            env_config["DB_CONN"] = {'host': env_config.get("DB_HOST", None),
                                     'port': int(env_config.get("DB_PORT", None))}
        except TypeError:
            env_config["DB_CONN"] = {'host': env_config.get("DB_HOST", None), 'port': None}
    return env_config


def load_configuration():
    """
    This loads configuration information and returns it to the process.
    """
    current_configs = envar_setup()
    toml_configs_path = current_configs["CONFIG_FILE"]
    toml_config = toml_setup(toml_configs_path)
    if toml_config:
        return toml_flatten(toml_config)

    return pythonize_env(current_configs)
