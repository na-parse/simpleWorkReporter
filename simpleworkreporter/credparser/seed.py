'''
credparser / seed.py

Provider for the master key seed
'''
import logging
import os
import secrets
import stat
from pathlib import Path
from .errors import InitFailure

_logger = logging.getLogger(__name__)


class MasterSeed():
    def __init__(self, allow_init: bool, seed_path: Path):
        '''
        Verify seed exists and can be read, otherwise initialize a new value.

        Note that decode operations are dependent on a master seed pre-existing
          so attempts to decode without an existing seed will raise
          as an InitFailure exception
        '''
        try:
            self._allow_init = bool(allow_init)
            self.seed_path = Path(seed_path)
            _logger.debug(
                f'MasterSeed init: path={self.seed_path}, allow_init={allow_init}'
            )

            if self.seed_path.exists():
                _logger.debug(f'Seed file exists: {self.seed_path}')
                # Verify that the seed data can be read
                _ = self.seed
                return

            _logger.debug(f'Seed file not found: {self.seed_path}')
            # Seed is not available
            if not allow_init:
                errmsg = (
                    f'Unable to initialize, master seed file not found: '
                    f'{str(self.seed_path)}'
                )
                raise InitFailure(errmsg)

            # Create a new seed
            self._create_credparser_dir()
            self._create_seed_file()

        except InitFailure:
            raise
        except Exception as e:
            raise InitFailure(f"Unexpected error during seed initialization: {e}")

    def __str__(self):
        return f'MasterSeed(seed_path={str(self.seed_path)})'

    def __repr__(self):
        return (
            f'MasterSeed(allow_init={self._allow_init}, '
            f'seed_path={str(self.seed_path)})'
        )


    @property
    def seed(self) -> bytes:
        ''' Read and return the master_seed value as bytes '''
        _logger.debug(f'Reading seed from {self.seed_path}')
        try:
            with open(self.seed_path, 'rb') as f:
                seed_data = f.read()
            _logger.debug(f'Seed read successfully, {len(seed_data)} bytes')
            return bytes(seed_data)

        except (OSError, PermissionError) as e:
            raise InitFailure(f"Failed to read seed file {self.seed_path}: {e}")


    def _create_credparser_dir(self) -> None:
        ''' Create the credparse seed storage directory '''
        # Get the parent (dir) for the master_seed file as a Path()
        seed_dir = Path(self.seed_path).parent
        _logger.debug(f'Creating seed directory: {seed_dir}')
        try:
            os.makedirs(seed_dir, mode=0o700, exist_ok=True)
            # Verify permissions in case directory already existed
            current_mode = stat.S_IMODE(os.stat(seed_dir).st_mode)
            if current_mode != 0o700:
                _logger.debug(
                    f'Adjusting directory permissions from {oct(current_mode)} to 0o700'
                )
                os.chmod(seed_dir, 0o700)
            _logger.debug(f'Seed directory ready: {seed_dir}')
        except (OSError, PermissionError) as e:
            errmsg = f"Failed to create/secure directory {str(seed_dir)}: {e}"
            raise InitFailure(errmsg)

    def _create_seed_file(self) -> None:
        ''' Create the credparse master seed file '''
        # Ensure pathlib.Path class format for seed_path
        seed_path = Path(self.seed_path)
        _logger.warning(f'Initializing new master seed: {seed_path}')
        try:
            if os.path.exists(seed_path):
                errmsg = f'Attempting to reinitialize existing seed: {str(self.seed_path)}'
                raise InitFailure(errmsg)

            # Create new seed file
            _logger.debug('Generating 1024 bytes of random seed data')
            seed_data = secrets.token_bytes(1024)

            # Set umask temporarily to ensure secure creation
            old_umask = os.umask(0o077)
            try:
                _logger.debug(f'Writing seed file: {seed_path}')
                with open(seed_path, 'wb') as f:
                    f.write(seed_data)
            finally:
                os.umask(old_umask)

            # Verify/set file permissions
            current_mode = stat.S_IMODE(os.stat(seed_path).st_mode)
            if current_mode != 0o600:
                _logger.debug(
                    f'Adjusting file permissions from {oct(current_mode)} to 0o600'
                )
                os.chmod(seed_path, 0o600)
            _logger.debug(f'Seed file created successfully: {seed_path}')

        except (OSError, PermissionError) as e:
            raise InitFailure(f"Failed to create/secure seed file {seed_path}: {e}")
