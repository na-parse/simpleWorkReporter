'''
credparser / config.py

Configuration module handling and defining configurable elements

Default values are defined as module level attributes and are based on best
recommendations.  Deployments that desire/require deviations can create the
'.config' file in the module directory.

Config settings:
    SALT_LEN = <length_for_salt>
    MAX_HASH_ROUNDS = <Maximum number of key-gen hash rounds>
    MIN_HASH_ROUNDS = <Minimum number of key-gen hash rounds>
'''
import logging
from dataclasses import dataclass
from pathlib import Path
from .errors import ConfigError

_logger = logging.getLogger(__name__)

# =============================================================================
# Default Configuration Values
# =============================================================================
CREDPARSER_CONFIG_FILE = Path(__file__).parent / '.config'
DEFAULT_SALT_LEN = 12
DEFAULT_MAX_HASH_ROUNDS = 24
DEFAULT_MIN_HASH_ROUNDS = 3

# =============================================================================
# Minimum Limit Constants (enforced during validation)
# =============================================================================
LIMIT_MIN_SALT_LEN = 8
LIMIT_MIN_HASH_ROUNDS = 1


# =============================================================================
# Configuration Dataclass
# =============================================================================
@dataclass(frozen=True)
class CredParserConfig:
    '''
    Configuration container for the CredParser module.

    Immutable dataclass holding configuration values. Use load_config() factory
    function to create instances with validation and config file support.

    Attributes:
        salt_len: Length setting for salt value (must be >= 8)
        max_hash_rounds: Maximum number of key-gen hash rounds
        min_hash_rounds: Minimum number of key-gen hash rounds (must be >= 1)
        config_file: Path to config file used (for reference/debugging)
    '''
    salt_len: int
    max_hash_rounds: int
    min_hash_rounds: int
    config_file: Path

    def __post_init__(self):
        '''Validate configuration values after initialization.'''
        errors = []
        if self.salt_len < LIMIT_MIN_SALT_LEN:
            errors.append(
                f'Salt length must be >= {LIMIT_MIN_SALT_LEN}: {self.salt_len}'
            )
        if self.min_hash_rounds < LIMIT_MIN_HASH_ROUNDS:
            errors.append(
                f'Minimum hash rounds must be >= {LIMIT_MIN_HASH_ROUNDS}: '
                f'{self.min_hash_rounds}'
            )
        if self.min_hash_rounds > self.max_hash_rounds:
            errors.append(
                f'Minimum hash rounds cannot be greater than max: '
                f'max={self.max_hash_rounds}, min={self.min_hash_rounds}'
            )
        if errors:
            raise ConfigError(' - '.join(errors))


# =============================================================================
# Config File Parsing
# =============================================================================
def _read_config_file(config_file: Path) -> dict:
    '''
    Reads the specified config file and returns a dictionary of all
    key = value lines found in the config file.
    '''
    if config_file is None or not Path(config_file).exists():
        _logger.debug(f'Config file not found: {config_file}')
        return {}

    _logger.debug(f'Reading config file: {config_file}')
    try:
        settings = {}
        with open(config_file, 'r') as f:
            lines = [
                line.strip() for line in f.readlines()
                if '=' in line and not line.startswith('#')
            ]
        for line in lines:
            key, value = [s.strip() for s in line.split('=')]
            key = key.lower()
            value = value.strip('\'"')
            if value.isdigit():
                value = int(value)
            settings[key] = value
            _logger.debug(f'Config file setting: {key}={value}')

        return settings

    except (OSError, PermissionError) as e:
        errmsg = f'Unable to read configuration file {config_file}: {e}'
        raise ConfigError(errmsg)


def _resolve_value(arg_value, config_value, default_value):
    '''Returns the highest priority value: arg > config file > default.'''
    if arg_value is not None:
        return arg_value
    if config_value is not None:
        return config_value
    return default_value


# =============================================================================
# Factory Function
# =============================================================================
def load_config(
    salt_len: int = None,
    max_hash_rounds: int = None,
    min_hash_rounds: int = None,
    config_file: Path = None
) -> CredParserConfig:
    '''
    Load and validate configuration, returning an immutable CredParserConfig.

    Priority order for each setting: argument > config file > default

    Args:
        salt_len: Override salt length
        max_hash_rounds: Override maximum hash rounds
        min_hash_rounds: Override minimum hash rounds
        config_file: Path to config file (default: module_dir/.config)

    Returns:
        CredParserConfig: Validated, immutable configuration object

    Raises:
        ConfigError: Invalid configuration values
    '''
    config_path = Path(config_file or CREDPARSER_CONFIG_FILE)
    _logger.debug(f'Loading config from: {config_path}')

    file_settings = _read_config_file(config_path)

    try:
        resolved_salt_len = int(_resolve_value(
            salt_len, file_settings.get('salt_len'), DEFAULT_SALT_LEN
        ))
        resolved_max_hash = int(_resolve_value(
            max_hash_rounds, file_settings.get('max_hash_rounds'), DEFAULT_MAX_HASH_ROUNDS
        ))
        resolved_min_hash = int(_resolve_value(
            min_hash_rounds, file_settings.get('min_hash_rounds'), DEFAULT_MIN_HASH_ROUNDS
        ))
    except ValueError as e:
        errmsg = f'Bad configuration value assignment in {config_path}: {e}'
        raise ConfigError(errmsg)

    config = CredParserConfig(
        salt_len=resolved_salt_len,
        max_hash_rounds=resolved_max_hash,
        min_hash_rounds=resolved_min_hash,
        config_file=config_path
    )

    _logger.debug(
        f'Config loaded: salt_len={config.salt_len}, '
        f'max_hash_rounds={config.max_hash_rounds}, '
        f'min_hash_rounds={config.min_hash_rounds}'
    )

    return config


# =============================================================================
# Module-level Singleton
# =============================================================================
config = load_config()
