"""Safe key/model diagnostics. --extract additionally makes one generation call."""
import argparse
import os
from config import ConfigError, load_config
from preference_agent import AIError, gemini_model_info, parse_preferences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true',
                        help='Also send one fixed fictional description using the real extraction schema; consumes API quota')
    args = parser.parse_args()
    print('RMR Gemini diagnostics (no key, prompt text, or raw provider error is printed).')
    try:
        config = load_config()
        print('Model:', config.model)
        print('Key source:', 'environment variable (overrides .env)' if 'GEMINI_API_KEY' in os.environ else '.env file')
        if not config.api_key:
            print('FAIL: No key is configured. Update .env beside main.py.')
            return 1
        print('Key present: yes. Checking Google model metadata; this does not generate text.')
        info = gemini_model_info(config)
        if not isinstance(info, dict) or info.get('name') != 'models/' + config.model:
            print('FAIL: Unexpected model metadata response.')
            return 1
        methods = info.get('supportedGenerationMethods', [])
        if not isinstance(methods, list) or 'generateContent' not in methods:
            print('FAIL: This model does not advertise generateContent access.')
            return 1
        print('PASS: Google accepted the metadata request and the model advertises generateContent.')
        print('This does not verify generation quota, schema acceptance, or billing tier.')
        if args.extract:
            result = parse_preferences({'text': 'Alex likes rice.'}, config=config)
            print('PASS: One generation returned structurally valid preferences.')
            print('Semantic accuracy was not checked. Review model outputs before recipe search.')
        else:
            print('Next: py -3 diagnose_gemini.py --extract (one generation request).')
        return 0
    except ConfigError as exc:
        print('FAIL [configuration]:', str(exc))
        return 1
    except AIError as exc:
        print('FAIL [' + exc.code + ']:', str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
