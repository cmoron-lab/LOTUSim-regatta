#!/usr/bin/env bash
# Brings a clean Ubuntu 24.04 (including WSL2) to a runnable regatta: the LOTUSim
# core at regatta-base in its own workspace, and this repository built as a colcon
# overlay on top of it. Idempotent: re-running it rebuilds, it does not re-clone.
#
#   ./install.sh          then open a new shell and: ./scripts/run_regatta.sh 300 smoke
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'
die() { echo -e "${RED}$*${NC}" >&2; exit 1; }
ok()  { echo -e "${GREEN}$*${NC}"; }

[[ "$(lsb_release -rs)" == "24.04" ]] || die "Ubuntu 24.04 required (ROS 2 Jazzy); found $(lsb_release -rs)"
[[ "$(uname -m)" == "x86_64" ]]       || die "x86_64 required: physics/xdyn-for-cs is an x86-64 binary"

REGATTA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOTUSIM_WS="${LOTUSIM_WS:-$HOME/lotusim_ws}"
export LOTUSIM_PATH="$LOTUSIM_WS/src/LOTUSim"

if [[ ! -d "$LOTUSIM_PATH" ]]; then
  mkdir -p "$LOTUSIM_WS/src"
  git clone -b regatta-base https://github.com/cmoron-lab/LOTUSim.git "$LOTUSIM_PATH"
fi

export PATH="$LOTUSIM_PATH/launch:$PATH"
# install_lotus, not install: `install` also pulls nvm + Node 18 for the web UI,
# which the regatta never runs. And no `sudo -E` around it -- the script sudo's
# install_dep.sh by itself, so colcon still builds as the user instead of leaving
# a root-owned build/ and install/ behind.
lotusim install_lotus
ok "core installed"

# ROS setup files read unset variables; -u must be off while sourcing them.
set +u
source "$LOTUSIM_WS/install/setup.bash"
cd "$REGATTA_ROOT" && colcon build --symlink-install
source "$REGATTA_ROOT/install/setup.bash"
set -u
ok "overlay built"

# Deliberately NOT written to ~/.bashrc: the user's interactive shell is theirs,
# and half of them run zsh, where the ROS setup.bash files break outright.
ok "done. To use it in a shell (bash or zsh):"
echo "    . $REGATTA_ROOT/env.sh"
echo
echo "  The harness sources it on its own, so this works from a bare shell:"
echo "    $REGATTA_ROOT/scripts/run_regatta.sh 300 smoke"
