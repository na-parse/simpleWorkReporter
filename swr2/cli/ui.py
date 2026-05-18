'''Shared terminal UI helpers for command-line workflows.'''

from __future__ import annotations

import getpass
import shutil
from collections.abc import Callable


class TerminalUI:
    '''Small prompt and formatting helper for setup-style CLI flows.'''

    def __init__(self) -> None:
        self.width = min(shutil.get_terminal_size((78, 24)).columns, 88)

    def header(self, title: str) -> None:
        print()
        print('=' * self.width)
        print(title.center(self.width))
        print('=' * self.width)

    def section(self, title: str) -> None:
        print()
        print(title)
        print('-' * min(len(title), self.width))

    def note(self, message: str = '') -> None:
        print(message)

    def success(self, message: str) -> None:
        print(f'[OK] {message}')

    def warning(self, message: str) -> None:
        print(f'[WARN] {message}')

    def error(self, message: str) -> None:
        print(f'[ERROR] {message}')

    def table(self, rows: list[tuple[str, str]]) -> None:
        if not rows:
            return
        label_width = min(max(len(label) for label, _ in rows), 24)
        for label, value in rows:
            print(f'  {label.ljust(label_width)} : {value}')

    def choice(self, title: str, choices: list[tuple[str, str]], default: str) -> str:
        self.section(title)
        for key, label in choices:
            print(f'  {key}) {label}')
        while True:
            value = self.input('Select', default).lower()
            if value in {key for key, _ in choices}:
                return value
            self.error('Choose one of: ' + ', '.join(key for key, _ in choices))

    def input(
        self,
        label: str,
        current: str = '',
        *,
        required: bool = False,
        validator: Callable[[str], str] | None = None,
    ) -> str:
        while True:
            suffix = f' [{current}]' if current else ''
            value = input(f'{label}{suffix}: ').strip()
            if not value:
                value = current
            if required and not value.strip():
                self.error('This value is required.')
                continue
            if validator is not None and value:
                try:
                    value = validator(value)
                except ValueError as exc:
                    self.error(str(exc))
                    continue
            return value

    def password(self, label: str) -> str:
        return getpass.getpass(f'{label}: ')

    def confirm(self, label: str, default: bool) -> bool:
        default_text = 'Y/n' if default else 'y/N'
        while True:
            value = input(f'{label} [{default_text}]: ').strip().lower()
            if not value:
                return default
            if value in {'y', 'yes'}:
                return True
            if value in {'n', 'no'}:
                return False
            self.error("Enter 'y' or 'n'.")
