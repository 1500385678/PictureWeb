"""
start_detached.py · PictureWeb 永驻启动器
- 用 CREATE_BREAKAWAY_FROM_JOB 脱离 mavis 父级 job
- 启动 server.py 子进程(也 detached)
- 父进程当 watchdog:每 30s 检查,死了自动拉
- 整个进程树跟 mavis 无关,mavis 退掉也不影响

用法:
  python start_detached.py            # 前台跑(可作 watchdog)
  python start_detached.py --once     # 只启动 server,自己不守
  python start_detached.py --stop     # 杀掉 server + 退
"""
import os
import sys
import time
import signal
import subprocess
import atexit

WD = r"D:\Mac\Mac\Mac\workteam\05_space\03_architect\Mobile\_ArchitectMobileLib\PictureWeb"
PY = r"C:\Users\yongzhang\AppData\Local\Programs\Python\Python312\python.exe"
PORT = "9004"
LOG_OUT = os.path.join(WD, "logs", "server.out.log")
LOG_ERR = os.path.join(WD, "logs", "server.err.log")
CHECK_INTERVAL = 30  # 秒


def kill_existing():
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr ":{PORT} " | findstr LISTENING',
            shell=True, text=True, timeout=5,
        )
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5:
                pid = parts[-1]
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                print(f"  killed old pid {pid}")
    except subprocess.CalledProcessError:
        pass
    except subprocess.TimeoutExpired:
        pass


def spawn_server():
    """启动 server,detached 标志脱离任何 job"""
    flags = (
        subprocess.CREATE_BREAKAWAY_FROM_JOB
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.DETACHED_PROCESS
    )
    env = os.environ.copy()
    env["PICTUREWEB_TEST_PORT"] = PORT
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    p = subprocess.Popen(
        [PY, "-X", "utf8", "server.py"],
        cwd=WD,
        env=env,
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=open(LOG_OUT, "ab"),
        stderr=open(LOG_ERR, "ab"),
        close_fds=True,
    )
    return p.pid


def is_alive(pid):
    # 关键:不用 text=True(UTF-8 解码中文 cp936 字节会 UnicodeDecodeError)
    # 改用 bytes 模式 + errors='replace' 兜底
    try:
        out = subprocess.check_output(
            f'tasklist /FI "PID eq {pid}"', shell=True, timeout=5,
        )
        return str(pid).encode() in out
    except Exception:
        return False


def port_listening():
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr ":{PORT} " | findstr LISTENING',
            shell=True, timeout=5,
        )
        return b"LISTENING" in out
    except Exception:
        return False


def main():
    args = sys.argv[1:]

    if "--stop" in args:
        kill_existing()
        print("stopped")
        return

    # --daemonize:用 breakaway 把本进程自己脱离父级 job,然后让"子进程"做 watchdog
    if "--daemonize" in args:
        flags = (
            subprocess.CREATE_BREAKAWAY_FROM_JOB
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
        )
        # 重新启动自己(不带 --daemonize),完全脱离 mavis 父级
        p = subprocess.Popen(
            [PY, "-X", "utf8", __file__],
            cwd=WD,
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=open(LOG_OUT, "ab"),
            stderr=open(LOG_ERR, "ab"),
            close_fds=True,
        )
        print(f"detached watchdog started: pid={p.pid}")
        print(f"  (mavis 父级退出后,这个 watchdog 仍存活)")
        return

    print(f"=== PictureWeb 永驻启动器 ===")
    print(f"  PORT     : {PORT}")
    print(f"  WD       : {WD}")
    print(f"  LOG      : {LOG_OUT}")
    print(f"  PID      : {os.getpid()}")

    kill_existing()
    pid = spawn_server()
    print(f"  started  : pid={pid}")

    if "--once" in args:
        print("  --once   : 不守护,启动完退出")
        return

    print(f"  watchdog : 每 {CHECK_INTERVAL}s 检查,死了自动拉")

    fail_streak = 0
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            if is_alive(pid) and port_listening():
                fail_streak = 0
            else:
                fail_streak += 1
                print(f"  [{time.strftime('%H:%M:%S')}] server pid={pid} 异常 (streak={fail_streak})")
                if fail_streak >= 2:
                    print(f"  → 重启 server")
                    kill_existing()
                    pid = spawn_server()
                    print(f"  → new pid={pid}")
                    fail_streak = 0
    except KeyboardInterrupt:
        print("  interrupted, leaving server running")


if __name__ == "__main__":
    main()
