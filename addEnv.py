'''
Find all dirs containing any specified file types, and add these dirs to an environment variable.
The default mode finds all exe files' dirs and add them as %CUSTOM%, so you won't need to manually add CLI programs to PATH.
Alternatively, you can use '-r' to generate a registry file (.reg) so as to share with different machines.
Only works on Windows.
'''

import os; assert os.name == 'nt'
import sys; assert sys.version_info >= (3, 6)
import argparse
from pathlib import Path
from operator import methodcaller
from winreg import ConnectRegistry, OpenKey, QueryValueEx, SetValueEx, HKEY_CURRENT_USER, KEY_ALL_ACCESS

DEFAULT_SUFFIX = ['.exe']


def addPath(path: Path, suffix: list[str]) -> list[Path]:
    ret = []
    if path.is_file() and (path.suffix.lower() in suffix):
        ret += [path.parent.resolve()]
    elif path.is_dir():
        items = tuple(path.iterdir())
        for f in filter(methodcaller('is_file'), items):
            if f.suffix.lower() in suffix:
                ret += [path.resolve()]
                break
        for d in filter(methodcaller('is_dir'), items):
            ret += addPath(d, suffix)
    return ret


def Main(args):

    if not args.suffix:
        args.suffix = DEFAULT_SUFFIX
    else:
        args.suffix = [s.lower() for s in args.suffix]

    paths = []
    for path in map(Path, args.paths):
        paths += addPath(path, args.suffix)
    paths += list(map(Path, args.manual_paths))
    paths = ';'.join(str(p) for p in sorted(paths))

    if args.out_registry:
        entry = 'Windows Registry Editor Version 5.00\r\n\r\n' \
              + '[HKEY_CURRENT_USER\\Environment]\r\n' \
              + f'"{args.varname}"=hex(2):' \
              + ','.join(f'{c:02x}' for c in paths.encode('utf-16-le')) \
              + '\r\n'
        Path(f'{args.varname}.reg').write_bytes(entry.encode('utf-16-le'))
        input(f'Saved paths to \'{args.varname}.reg\'.')
    else:
        with ConnectRegistry(None, HKEY_CURRENT_USER) as reg:
            with OpenKey(reg, 'Environment', access=KEY_ALL_ACCESS) as env: # Admin not required
                try:
                    if QueryValueEx(env, args.varname) and args.prompt:
                        input(f"Error: The variable '{args.varname}' already exists. "
                               "Consider adding '-y' argument to overwrite it.")
                        sys.exit()
                except FileNotFoundError as e:
                    if e.winerror == 2: # indicating this key not exists, so just ignore
                        pass
                    else:
                        raise e
                SetValueEx(env, args.varname, 0, 2, paths)
                input(f"Written paths to 'HEKY_CURRENT_USER\\Environment\\{args.varname}'.\n"
                      f"You can now add '%{args.varname}%' to PATH to make it effective.")

class _CustomHelpFormatter(argparse.HelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=50, width=100)
    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ', '.join(action.option_strings) + ' ' + args_string

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='AddEnv', formatter_class=lambda prog: _CustomHelpFormatter(prog))
    parser.add_argument('paths', type=Path, action='extend', nargs='+',
                        help='The paths to search', metavar='path')
    parser.add_argument('-e', '--ext', dest='suffix', type=str, action='extend', nargs='*', default=[],
                        help='to search for these file EXTensions and include their dirs', metavar='ext')
    parser.add_argument('-v', '--var', dest='varname', type=str, default='CUSTOM',
                        help='The dest environment VARiable name (default=CUSTOM)', metavar='var')
    parser.add_argument('-a', '--add', dest='manual_paths', type=str, action='extend', nargs='*', default=[],
                        help='manually ADD these paths to `var`', metavar='add')
    parser.add_argument('-r', '--registry', dest='out_registry', action='store_true', default=False,
                        help='generate a registry file instead of modifying environment now')
    parser.add_argument('-y', '--yes', dest='prompt', action='store_false', default=True,
                        help="don't prompt on overwritting")
    Main(parser.parse_args())
