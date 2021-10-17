import itertools
import sys
import time
import signal

import config

from .fancycli import fancywait
from .fancycli.platform import isatty


def skipcallback(handler):
    raise StopIteration

class ShellNextFrontend:
    def __init__(self, use_status_line, show_toggle):
        self.show_toggle = show_toggle
        self.use_status_line = use_status_line
        if use_status_line:
            io = sys.stdout.buffer
            if hasattr(io, 'raw'):
                io = io.raw
            line = fancywait.StatusLine(io)
            self.statusline = line
    def attach(self, helper):
        self.helper = helper
    def alert(self, title, text, level='info', details=None):
        pass
    def notify(self, name, value):
        pass
    def delay(self, secs, allow_skip):
        if not self.use_status_line:
            time.sleep(secs)
            return
        if self.show_toggle:
            togglelabel = lambda: '<r>切换自动补充理智(%s)' % ('ON' if self.helper.addon('combat').use_refill else 'OFF')
            def togglecallback(handler):
                self.helper.addon('combat').use_refill = not self.helper.addon('combat').use_refill
                handler.label = togglelabel()
            togglehandler = lambda: fancywait.KeyHandler(togglelabel(), b'r', togglecallback)
        else:
            togglehandler = lambda: fancywait.KeyHandler(None, None, None)
        skiphandler = fancywait.KeyHandler('<ENTER>跳过', b'\r', skipcallback)
        skipdummy   = fancywait.KeyHandler('           ', b'', lambda x: None)
        fancywait.fancy_delay(secs, self.statusline, [skiphandler if allow_skip else skipdummy, togglehandler()])
    def request_device_connector(self):
        _ensure_device()
        return device

def _create_helper(use_status_line=True, show_toggle=False):
    from Arknights.helper import ArknightsHelper
    frontend = ShellNextFrontend(use_status_line, show_toggle)
    helper = ArknightsHelper(device_connector=device, frontend=frontend)
    if use_status_line:
        context = frontend.statusline
    else:
        from contextlib import nullcontext
        context = nullcontext()
    frontend.context = context
    return helper, context



class AlarmContext:
    def __init__(self, duration=60):
        self.duration = duration

    def __enter__(self):
        self.t0 = time.monotonic()

    def __exit__(self, exc_type, exc_val, exc_tb):
        t1 = time.monotonic()
        if t1 - self.t0 >= self.duration:
            self.alarm()

    def alarm(self):
        pass


class BellAlarmContext(AlarmContext):
    def alarm(self):
        print('\a', end='')


def _alarm_context_factory():
    if isatty(sys.stdout):
        return BellAlarmContext()
    return AlarmContext()


device = None


def connect(argv):
    """
    connect [connector type] [connector args ...]
        连接到设备
        支持的设备类型：
        connect adb [serial or tcpip endpoint]
    """
    connector_type = 'adb'
    if len(argv) > 1:
        connector_type = argv[1]
        connector_args = argv[2:]
    else:
        connector_args = []
    if connector_type == 'adb':
        _connect_adb(connector_args)
    else:
        print('unknown connector type:', connector_type)


def _connect_adb(args):
    from connector.ADBConnector import ADBConnector, ensure_adb_alive
    ensure_adb_alive()
    global device
    if len(args) == 0:
        try:
            device = ADBConnector.auto_connect()
        except IndexError:
            devices = ADBConnector.available_devices()
            if len(devices) == 0:
                print("当前无设备连接")
                raise
            print("检测到多台设备")
            for i, (serial, status) in enumerate(devices):
                print("%2d. %s\t[%s]" % (i, serial, status))
            num = 0
            while True:
                try:
                    num = int(input("请输入序号选择设备: "))
                    if not 0 <= num < len(devices):
                        raise ValueError()
                    break
                except ValueError:
                    print("输入不合法，请重新输入")
            device_name = devices[num][0]
            device = ADBConnector(device_name)
    else:
        serial = args[0]
        device = ADBConnector(serial)


def _ensure_device():
    if device is None:
        connect(['connect'])
    device.ensure_alive()


def interactive(argv):
    """
    interactive
        进入交互模式，减少按键次数（
    """
    import shlex
    import traceback
    helpcmds(interactive_cmds)
    errorlevel = None
    try:
        import readline
    except ImportError:
        pass
    if instance_id := config.get_instance_id():
        title = f"akhelper-{instance_id}"
    else:
        title = "akhelper"
    while True:
        try:
            if device is None:
                prompt = f"{title}> "
            else:
                prompt = f"{title} {str(device)}> "
            cmdline = input(prompt)
            argv = shlex.split(cmdline)
            if len(argv) == 0 or argv[0] == '?' or argv[0] == 'help':
                print(' '.join(x[0] for x in interactive_cmds))
                continue
            elif argv[0] == 'exit':
                break
            cmd = match_cmd(argv[0], interactive_cmds)
            if cmd is not None:
                with _alarm_context_factory():
                    errorlevel = cmd(argv)
        except EOFError:
            print('')  # print newline on EOF
            break
        except (Exception, KeyboardInterrupt) as e:
            errorlevel = e
            traceback.print_exc()
            continue
    return errorlevel


argv0 = 'placeholder'


def helpcmds(cmds):
    print("commands (prefix abbreviation accepted):")
    for cmd in cmds:
        if cmd[2]:
            print("    " + str(cmd[2].strip()))
        else:
            print("    " + cmd[0])


def help(argv):
    """
    help
        输出本段消息
    """
    print("usage: %s command [command args]" % argv0)
    helpcmds(global_cmds)


def exit(argv):
    sys.exit()

helper_cmds = []
global_cmds = []
interactive_cmds = []
helper_instance = None

def match_cmd(first, avail_cmds):
    targetcmd = [x for x in avail_cmds if x[0].startswith(first)]
    if len(targetcmd) == 1:
        return targetcmd[0][1]
    elif len(targetcmd) == 0:
        print("unrecognized command: " + first)
        return None
    else:
        print("ambiguous command: " + first)
        print("matched commands: " + ','.join(x[0] for x in targetcmd))
        return None

def main(argv):
    global argv0, helper_instance
    config.enable_logging()
    argv0 = argv[0]
    helper_instance, context = _create_helper()
    
    global_cmds.extend([*helper_instance._cli_commands, ('interactive', interactive, interactive.__doc__), ('help', help, help.__doc__)])
    interactive_cmds.extend([('connect', connect, connect.__doc__), *helper_instance._cli_commands, ('exit', exit, '')])
    if len(argv) < 2:
        interactive(argv[1:])
        return 1
    targetcmd = match_cmd(argv[1], global_cmds)
    if targetcmd is not None:
        return targetcmd(argv[1:])
    else:
        help(argv)
    return 1


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))

__all__ = ['main']
