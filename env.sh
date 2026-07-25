# Sets up the LOTUSim environment for the regatta. Source it, do not run it:
#
#     . ./env.sh          (bash or zsh, from anywhere)
#
# Nothing is written to ~/.bashrc or ~/.zshrc: an interactive shell is the user's,
# not ours. Sourcing twice is harmless.

# bash exposes this file as BASH_SOURCE[0]; zsh leaves that unset and puts the
# sourced path in $0.
_lr_self="${BASH_SOURCE[0]:-$0}"
_lr_root="$(cd "$(dirname "$_lr_self")" && pwd)"

export LOTUSIM_WS="${LOTUSIM_WS:-$HOME/lotusim_ws}"
export LOTUSIM_PATH="$LOTUSIM_WS/src/LOTUSim"

case ":$PATH:" in
  *":$LOTUSIM_PATH/launch:"*) ;;                 # already there
  *) export PATH="$LOTUSIM_PATH/launch:$PATH" ;;
esac

# ROS setup files ship one flavour per shell, and they are NOT interchangeable:
# sourcing setup.bash under zsh leaves ${BASH_SOURCE} empty, so the prefix
# resolves to $PWD and it dies looking for <cwd>/local_setup.sh.
if [ -n "${ZSH_VERSION:-}" ]; then _lr_ext=zsh; else _lr_ext=bash; fi

. "/opt/ros/${ROS_DISTRO:-jazzy}/setup.$_lr_ext"
. "$LOTUSIM_WS/install/setup.$_lr_ext"
# Absent until install.sh has built the overlay; the core alone is still usable.
[ -f "$_lr_root/install/setup.$_lr_ext" ] && . "$_lr_root/install/setup.$_lr_ext"

unset _lr_self _lr_root _lr_ext
