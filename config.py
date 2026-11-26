"""Read server-side Gemini settings without third-party packages or shell execution."""
from dataclasses import dataclass, field
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = 'gemini-3.5-flash-lite'
# Both have a published free tier when this release was prepared. Quotas and
# billing eligibility still belong to the user's Google project, not this app.
FREE_TIER_MODELS = {DEFAULT_MODEL, 'gemini-3.1-flash-lite'}
SETTING_NAMES = {'GEMINI_API_KEY', 'GEMINI_MODEL', 'GEMINI_TIMEOUT_SECONDS'}


class ConfigError(Exception):
    """Configuration error containing no secret values."""


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL
    timeout: int = 45


def read_env_file(path):
    """Read only supported KEY=value settings. Never source or evaluate a file."""
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise ConfigError('Cannot read .env. Check file permissions and UTF-8 encoding.') from exc
    settings = {}
    for number, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if not separator or name not in SETTING_NAMES or name in settings:
            raise ConfigError(f'Invalid or duplicate setting on .env line {number}. Use .env.example as the template.')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigError(f'Unclosed quote on .env line {number}.')
            value = value[1:-1]
        settings[name] = value
    return settings


def load_config(env=None, env_path=None):
    """Environment variables override .env; missing credentials permit manual use."""
    if env is None:
        env = os.environ
    path = BASE_DIR / '.env' if env_path is None else Path(env_path)
    values = read_env_file(path)
    for name in SETTING_NAMES:
        if name in env:
            values[name] = env[name]
    api_key = values.get('GEMINI_API_KEY', '').strip()
    if api_key.casefold() in {'paste_your_key_here', 'your_api_key_here', 'replace_me'}:
        api_key = ''
    if any(ch.isspace() for ch in api_key) or len(api_key) > 512 or any(ord(ch) < 33 or ord(ch) > 126 for ch in api_key):
        raise ConfigError('GEMINI_API_KEY must contain only the key, without whitespace or control characters.')
    model = values.get('GEMINI_MODEL', DEFAULT_MODEL).strip()
    if model not in FREE_TIER_MODELS:
        raise ConfigError('Choose GEMINI_MODEL=gemini-3.5-flash-lite or gemini-3.1-flash-lite. No model was substituted.')
    try:
        timeout = int(values.get('GEMINI_TIMEOUT_SECONDS', '45'))
    except ValueError as exc:
        raise ConfigError('GEMINI_TIMEOUT_SECONDS must be a whole number from 5 to 180.') from exc
    if not 5 <= timeout <= 180:
        raise ConfigError('GEMINI_TIMEOUT_SECONDS must be a whole number from 5 to 180.')
    return GeminiConfig(api_key=api_key, model=model, timeout=timeout)


def public_ai_status():
    """Local settings only: never reveal the key or spend a model request."""
    try:
        config = load_config()
    except ConfigError as exc:
        return {'provider': 'gemini', 'configured': False, 'model': DEFAULT_MODEL,
                'message': str(exc), 'connection_tested': False}
    return {'provider': 'gemini', 'configured': bool(config.api_key), 'model': config.model,
            'message': 'API key configured. Connection and quota have not been tested.' if config.api_key else
            'Add GEMINI_API_KEY to .env using .env.example, then retry. Manual entry is available.',
            'connection_tested': False}
