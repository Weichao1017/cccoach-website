#!/bin/bash
# 安全重启新站（JPress），用于模板改动生效。
# 不调用 jpress.sh 自带的 stop：它按“命令行里含程序路径”杀进程，远程调用时会连调用者一起杀掉。
# 做法：记下正在运行的 java 进程的完整启动命令和工作目录 → 停掉它 → 用同样的命令重新拉起 → 等首页恢复 200。
set -uo pipefail

PID=$(pgrep -f 'io\.jpress\.Starter$' | head -1 || true)
if [ -z "$PID" ]; then
  echo "没找到正在运行的新站进程"; exit 1
fi
mapfile -d '' CMD < /proc/"$PID"/cmdline
mapfile -d '' ENVV < /proc/"$PID"/environ
CMD[0]=$(readlink -f /proc/"$PID"/exe)   # 用正在运行的那个 java 的绝对路径
CWD=$(readlink -f /proc/"$PID"/cwd)

kill "$PID"
for i in $(seq 1 30); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
if kill -0 "$PID" 2>/dev/null; then kill -9 "$PID"; sleep 1; fi

cd "$CWD"
setsid nohup env -i "${ENVV[@]}" "${CMD[@]}" >/dev/null 2>&1 < /dev/null &   # 原样沿用原进程的环境变量

for i in $(seq 1 180); do
  code=$(curl -s -o /dev/null -m 5 -w "%{http_code}" -H "Host: www.cccoach.cn" http://127.0.0.1:8080/ || true)
  if [ "$code" = "200" ]; then echo "新站已启动（用时约 ${i} 秒）"; exit 0; fi
  sleep 1
done
echo "新站 180 秒内没有恢复"; exit 1
