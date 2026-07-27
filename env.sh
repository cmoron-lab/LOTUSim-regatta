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

# The ROS node and the gz smoke gate run on the SYSTEM interpreter -- rclpy and
# gz-transport come from apt, not from any venv -- and they import `regatta`. A
# single path entry is enough because that package has no dependencies of its own;
# uv serves the very same files to the offline side as an editable install.
case ":${PYTHONPATH:-}:" in
  *":$_lr_root/src:"*) ;;                        # already there
  *) export PYTHONPATH="$_lr_root/src${PYTHONPATH:+:$PYTHONPATH}" ;;
esac

# ROS setup files ship one flavour per shell, and they are NOT interchangeable:
# sourcing setup.bash under zsh leaves ${BASH_SOURCE} empty, so the prefix
# resolves to $PWD and it dies looking for <cwd>/local_setup.sh.
if [ -n "${ZSH_VERSION:-}" ]; then _lr_ext=zsh; else _lr_ext=bash; fi

. "/opt/ros/${ROS_DISTRO:-jazzy}/setup.$_lr_ext"
. "$LOTUSIM_WS/install/setup.$_lr_ext"
# Absent until install.sh has built the overlay; the core alone is still usable.
[ -f "$_lr_root/install/setup.$_lr_ext" ] && . "$_lr_root/install/setup.$_lr_ext"

# `lotusim` ships completion for its subcommands and flags, and for the xdyn
# binaries. It used to be sourced from the ~/.bashrc block that 021338e removed, and
# was never re-homed; env.sh is where it belongs. Interactive shells only -- the
# harness sources this file on every run and has no use for a compinit.
case "$-" in
  *i*)
    if [ -n "${ZSH_VERSION:-}" ]; then
      # The script speaks bash's completion API. zsh hosts it through bashcompinit,
      # whose `complete` shim calls compdef -- so compinit must have run first, or
      # every registration dies with "compdef: command not found".
      # ponytail: -u skips the insecure-directory prompt rather than stalling a
      # sourced file mid-way; most zshrc have run compinit already anyway.
      command -v compdef > /dev/null 2>&1 || { autoload -U +X compinit && compinit -u; }
      autoload -U +X bashcompinit && bashcompinit
    fi
    [ -f "$LOTUSIM_PATH/launch/bash_completion.sh" ] &&
      . "$LOTUSIM_PATH/launch/bash_completion.sh"

    # Interactive only, for the same reason: a summary is reassurance for a person,
    # and noise in the harness logs. Every line reports what was RESOLVED, not what
    # was attempted -- "overlay built" means the setup file was actually there.
    # Colours only on a tty, so `. ./env.sh > log` stays readable.
    if [ -t 1 ]; then
      _lr_g=$'\033[32m'; _lr_y=$'\033[33m'; _lr_d=$'\033[2m'; _lr_n=$'\033[0m'
    else
      _lr_g=; _lr_y=; _lr_d=; _lr_n=
    fi
    _lr_line() {  # <ok?0:1> <label> <value>
      if [ "$1" = 0 ]; then
        printf '  %s✓%s %-8s %s%s%s\n' "$_lr_g" "$_lr_n" "$2" "$_lr_d" "$3" "$_lr_n"
      else
        printf '  %s✗ %-8s %s%s\n' "$_lr_y" "$2" "$3" "$_lr_n"
      fi
    }
    printf '\n%sLOTUSim regatta%s %s%s%s\n' "$_lr_g" "$_lr_n" "$_lr_d" "$_lr_root" "$_lr_n"
    _lr_line 0 ROS "${ROS_DISTRO:-jazzy}"
    _lr_line 0 "core ws" "$LOTUSIM_WS"
    _lr_line 0 regatta "src/ on PYTHONPATH"
    if [ -f "$_lr_root/install/setup.$_lr_ext" ]; then
      _lr_line 0 overlay "built"
    else
      _lr_line 1 overlay "not built -- run ./install.sh"
    fi
    if command -v lotusim > /dev/null 2>&1; then
      _lr_line 0 lotusim "$(command -v lotusim)"
    else
      _lr_line 1 lotusim "not on PATH -- run ./install.sh"
    fi
    printf '\n'
    unset -f _lr_line
    unset _lr_g _lr_y _lr_d _lr_n
    ;;
esac

unset _lr_self _lr_root _lr_ext
