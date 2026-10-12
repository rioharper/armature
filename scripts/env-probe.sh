#!/usr/bin/env bash
# Environment probe: prints KEY=VALUE facts about the machine it runs on.
# Bash only (Git Bash on Windows). The agent runs this and writes the result
# into the project's docs/environment.md; see skills/init/SKILL.md.
#
#   bash scripts/env-probe.sh                      # core checks only
#   bash scripts/env-probe.sh ros2 gazebo cuda     # core plus a named tier
#
# Core is always checked: the working python invocation and whether SymPy,
# SciPy, NumPy and MuJoCo import under it (informational; derive needs uv); uv, git, gh; host, OS, bash, WSL.
#
# Each argument adds a check. ros2, colcon, gazebo, cuda, wsl, pinocchio and
# solidworks have real checks; any other name falls back to `command -v` plus
# `<name> --version`, so a spec can name a tool this script has never heard of.
#
# Absence is a value, never an error: a missing tool prints `absent` and the
# script still exits 0. What to do about a gap is the caller's judgement.

set -u

emit() { printf '%s=%s\n' "$1" "$2"; }

have() { command -v "$1" >/dev/null 2>&1; }

# First line of stdin, stripped of the CR that Windows tools append.
line1() { head -n 1 | tr -d '\r'; }

# emit <key> from `<cmd> <args...>`, or `absent` when cmd is missing.
tool() {
  local key="$1" cmd="$2"; shift 2
  if ! have "$cmd"; then emit "$key" absent; return; fi
  local out
  out=$("$cmd" "$@" 2>&1 | line1)
  emit "$key" "${out:-present}"
}

key_of() { printf '%s' "$1" | tr 'a-z-' 'A-Z_'; }

# --- core ---------------------------------------------------------------

emit HOST "$(hostname 2>/dev/null || echo unknown)"
emit PROBED "$(date +%Y-%m-%d)"

uname_s=$(uname -s 2>/dev/null || echo unknown)
case "$uname_s" in
  MINGW*|MSYS*|CYGWIN*) OS_KIND=windows ;;
  Linux*)               OS_KIND=linux   ;;
  Darwin*)              OS_KIND=macos   ;;
  *)                    OS_KIND=unknown ;;
esac
emit OS_KIND "$OS_KIND"
emit OS "$(uname -sr 2>/dev/null || echo unknown)"
emit BASH_VERSION "${BASH_VERSION:-unknown}"

# The invocation that works, not merely whether `python` is on PATH — a
# machine with python installed under `py` reads as absent to anything that
# only tries `python`.
PY=absent
py_version=absent
for c in python python3 py; do
  have "$c" || continue
  v=$("$c" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null) || continue
  [ -n "$v" ] || continue
  PY=$c
  py_version=$v
  break
done
emit PYTHON "$PY"
emit PYTHON_VERSION "$py_version"

# One interpreter start for all of them, and a failed import says which kind of
# failure it was: a module that is not installed reads `absent`, one that is
# installed but will not load reads `error: <Type>`. Collapsing both into
# `absent` would send someone to install what is already there.
py_modules() {
  if [ "$PY" = absent ]; then
    for m in "$@"; do emit "$(key_of "$m")" absent; done
    return
  fi
  "$PY" - "$@" <<'MODCHECK' 2>/dev/null && return
import sys
for name in sys.argv[1:]:
    try:
        mod = __import__(name)
        value = getattr(mod, "__version__", "present")
    except ModuleNotFoundError:
        value = "absent"
    except BaseException as exc:
        value = "error: %s" % type(exc).__name__
    print("%s=%s" % (name.upper(), value))
MODCHECK
  for m in "$@"; do emit "$(key_of "$m")" unknown; done
}

# These say only what an ad hoc script outside a project's model can import.
# armature-derive runs in analysis/model's own uv environment, which pins the
# engine and its MuJoCo, so UV below is what a derivation checkpoint needs.
py_modules sympy scipy numpy mujoco

tool UV  uv  --version
tool GIT git --version
tool GH  gh  --version

# --- named checks -------------------------------------------------------

check_wsl() {
  if [ "$OS_KIND" != windows ]; then emit WSL "n/a"; return; fi
  if ! have wsl.exe; then emit WSL absent; return; fi
  local distros
  distros=$(wsl.exe -l -q 2>/dev/null | tr -d '\0\r' | grep -v '^$' | paste -sd, -)
  emit WSL "${distros:-present}"
}

check_ros2() {
  if ! have ros2; then emit ROS2 absent; return; fi
  emit ROS2 "${ROS_DISTRO:-$(ros2 --version 2>&1 | line1)}"
}

check_colcon() { tool COLCON colcon version-check; }

check_gazebo() {
  if have gz; then emit GAZEBO "$(gz sim --version 2>&1 | line1)"
  elif have gazebo; then emit GAZEBO "$(gazebo --version 2>&1 | line1)"
  else emit GAZEBO absent
  fi
}

check_cuda() {
  if have nvidia-smi; then
    emit GPU "$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | line1)"
    emit CUDA_DRIVER "$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | line1)"
  else
    emit GPU absent
    emit CUDA_DRIVER absent
  fi
  if have nvcc; then
    emit CUDA_TOOLKIT "$(nvcc --version 2>&1 | grep -i release | line1)"
  else
    emit CUDA_TOOLKIT absent
  fi
}

# Installed, which is durable and worth recording. Whether SOLIDWORKS is
# *running* is true only while the CAD checks run, so init asks that live
# rather than reading it here.
# No skill uses Pinocchio: the truth model is the engine's, MuJoCo only. The
# check stays for a spec that names it for work of its own. There is no
# Windows pip wheel, so it arrives by conda or WSL or not at all.
check_pinocchio() { py_modules pinocchio; }

check_solidworks() {
  if [ "$OS_KIND" != windows ]; then emit SOLIDWORKS "n/a"; return; fi
  local d
  for d in "/c/Program Files/SOLIDWORKS Corp/SOLIDWORKS" \
           "/c/Program Files/SolidWorks Corp/SolidWorks"; do
    if [ -d "$d" ]; then emit SOLIDWORKS "installed"; return; fi
  done
  emit SOLIDWORKS absent
}

for name in "$@"; do
  case "$name" in
    wsl)        check_wsl ;;
    ros2)       check_ros2 ;;
    colcon)     check_colcon ;;
    gazebo|gz)  check_gazebo ;;
    cuda|gpu)   check_cuda ;;
    pinocchio)  check_pinocchio ;;
    solidworks) check_solidworks ;;
    *)          tool "$(key_of "$name")" "$name" --version ;;
  esac
done

exit 0
