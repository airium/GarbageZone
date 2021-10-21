'''
Find all directories containing certain file types, and add these directories to a variable in environment.
Only designed for Windows.
'''

import os
assert os.name == 'nt'
import sys
assert sys.version_info >= (3, 6)

import argparse
from pathlib import Path
from operator import methodcaller
from winreg import ConnectRegistry, OpenKey, QueryValueEx, SetValueEx, HKEY_CURRENT_USER, KEY_ALL_ACCESS


def addPath(path: Path, add_if: list[str]) -> list[Path]:
    ret = []
    if path.is_file() and (path.suffix.lower() in add_if):
        ret += [path.parent.resolve()]
    elif path.is_dir():
        items = tuple(path.iterdir())
        for f in filter(methodcaller('is_file'), items):
            if f.suffix.lower() in add_if:
                ret += [path.resolve()]
                break
        for d in filter(methodcaller('is_dir'), items):
            ret += addPath(d, add_if)
    return ret


def Main(args):
    paths = []
    for path in map(Path, args.paths):
        paths += addPath(path, args.add_if)
    paths += list(map(Path, args.manual_paths))
    env = OpenKey(ConnectRegistry(None, HKEY_CURRENT_USER), 'Environment', access=KEY_ALL_ACCESS) # Admin not required
    try:
        if QueryValueEx(env, args.varname) and args.prompt:
            input(f"Error: The variable '{args.varname}' already exists.\n"
                   "Consider adding '-y' argument to overwrite it.")
            sys.exit()
    except FileNotFoundError as e:
        if e.winerror == 2:
            pass
        else:
            raise e
    SetValueEx(env, args.varname, 0, 2, ';'.join(str(p) for p in paths))
    input(f"Successfully written paths to 'HEKY_CURRENT_USER\\Environment\\{args.varname}'.\n"
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
    parser.add_argument('-e', '--ext', dest='add_if', type=str, action='extend', nargs='*', default=['.exe'],
                        help='to search for these file EXTensions and include their dirs', metavar='ext')
    parser.add_argument('-v', '--var', dest='varname', type=str, default='CUSTOM',
                        help='The dest environment VARiable name (default=CUSTOM)', metavar='var')
    parser.add_argument('-a', '--add', dest='manual_paths', type=str, action='extend', nargs='*', default=[],
                        help='manually ADD these paths', metavar='add')
    parser.add_argument('-y', '--yes', dest='prompt', action='store_false', default=True,
                        help="don't prompt on overwritting")
    Main(parser.parse_args())
