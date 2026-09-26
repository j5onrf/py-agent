#!/usr/bin/env bash
# Production Py-Agent Shell Hook v0.9.9.40 (Hardened & Production Ready)

[[ $- == *i* && -f "$HOME/.config/py-agent/ai-agent.py" ]] || return 0 2>/dev/null || exit 0

_AI_DIR="$HOME/.config/py-agent"
_AI_PY="${_AI_PY:-$(command -v python3 || command -v python)}"

# 1. Strict Python 3.8+ Version Probe
if [[ -z "$_AI_PY" ]] || ! "$_AI_PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    echo "py-agent: Python 3.8+ is required but not found on PATH." >&2
    return 1 2>/dev/null || exit 1
fi

# 2. Atomic Shell Teleportation
_ai_teleport() {
    local f="$_AI_DIR/.active_cd.$$"
    if [[ -f "$f" ]]; then
        local target
        target=$(head -n 1 "$f" 2>/dev/null)
        rm -f "$f"
        [[ -n "$target" && -d "$target" ]] && cd "$target" 2>/dev/null
    fi
}

if [[ -n "$ZSH_VERSION" ]]; then
    autoload -Uz add-zsh-hook 2>/dev/null && add-zsh-hook precmd _ai_teleport
elif [[ -n "$BASH_VERSION" ]]; then
    if [[ "$PROMPT_COMMAND" != *_ai_teleport* ]]; then
        PROMPT_COMMAND="_ai_teleport${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
    fi
fi

# 3. Intent & Missing Command Handler
ai_handle_missing() {
    local cmd exp
    cmd=$([[ -n "$*" ]] && "$_AI_PY" "$_AI_DIR/ai-agent.py" --interactive "$*") || return 127
    [[ -z "$cmd" ]] && return 127

    # Comprehensive ANSI and OSC escape sequence stripper
    exp=$(printf '%s' "$cmd" | sed -E $'s/\x1b\\][^\x07\x1b]*(\x07|\x1b\\\\)|\x1b\\[[0-9;?]*[a-zA-Z~]|\r//g')

    # Safe tilde expansion
    if [[ "$exp" == "~" ]]; then
        exp="$HOME"
    elif [[ "$exp" == "~/"* ]]; then
        exp="${HOME}/${exp#\~/}"
    fi

    if [[ -d "$exp" ]]; then
        ai init "$exp"
    elif [[ "$exp" == *.py && -f "$exp" ]]; then
        "$_AI_PY" "$exp"
    else
        # Syntax check using active interpreter (zsh or bash)
        if [[ -n "$ZSH_VERSION" ]]; then
            if ! zsh -n <<< "$exp" 2>/dev/null; then
                echo "py-agent: invalid shell syntax in command" >&2
                return 127
            fi
        else
            if ! bash -n <<< "$exp" 2>/dev/null; then
                echo "py-agent: invalid shell syntax in command" >&2
                return 127
            fi
        fi

        eval "$exp"
    fi
}

# 4. Command Not Found Hooks with Re-Entrancy Guard
command_not_found_handle() {
    [[ -n "${_AI_CNF_ACTIVE:-}" ]] && return 127
    [[ "${1:-}" != --* ]] || return 127
    local rc=127
    _AI_CNF_ACTIVE=1 ai_handle_missing "$@" && rc=0
    return "$rc"
}
command_not_found_handler() { command_not_found_handle "$@"; }

# 5. Primary AI Shell Wrapper
ai() {
    # Portable nullglob: avoid zsh NOMATCH aborts when no lockfiles exist
    local old files=()
    if [[ -n "$ZSH_VERSION" ]]; then
        files=("$_AI_DIR"/.active_cd.*(N))
    else
        local nullglob_set=0
        shopt -q nullglob && nullglob_set=1
        shopt -s nullglob
        files=("$_AI_DIR"/.active_cd.*)
        [[ "$nullglob_set" -eq 0 ]] && shopt -u nullglob
    fi

    for old in "${files[@]}"; do
        [[ -e "$old" ]] || continue
        local pid="${old##*.active_cd.}"
        if [[ "$pid" =~ ^[0-9]+$ ]]; then
            if ! kill -0 "$pid" 2>/dev/null; then
                rm -f "$old"
            elif [[ -f "/proc/$pid/comm" ]] && ! grep -qE '(bash|zsh|sh)$' "/proc/$pid/comm" 2>/dev/null; then
                rm -f "$old"
            fi
        else
            rm -f "$old"
        fi
    done

    if [[ "$1" == "init" ]]; then
        shift
        local path skills=() name map db
        path=$(pwd)

        if [[ -n "${1:-}" && "$1" != -* ]]; then
            path="$1"
            shift
        fi
        skills=("$@")

        [[ -d "$path" ]] || mkdir -p "$path" 2>/dev/null
        path=$(CDPATH= cd "$path" 2>/dev/null && pwd -P) || return 1

        local lockfile="$_AI_DIR/.active_cd.$$"
        echo "$path" > "$lockfile"
        name=$(basename "$path")

        local cfg="$path/.agent/config.json"
        local use_map=0
        if [[ -f "$cfg" ]]; then
            if "$_AI_PY" -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    sys.exit(0 if (str(d.get("map", "")).lower() in ("true", "1", "yes") or "-map" in str(d.get("profile", "")).lower()) else 1)
except Exception:
    sys.exit(1)
' "$cfg" 2>/dev/null; then
                use_map=1
            fi
        fi

        if [[ "$use_map" -eq 1 ]]; then
            map="$path/.agent/index-map-$name.txt"; [[ -f "$map" ]] || map="$path/index-map-$name.txt"
            db="$path/.agent/index-map-memory-$name.db"; [[ -f "$db" ]] || db="$path/index-map-memory-$name.db"

            local needs_compile=0
            if [[ ! -f "$map" || ! -f "$db" || "$path" -nt "$map" ]]; then
                needs_compile=1
            elif git -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
                [[ -n "$(git -C "$path" status --porcelain 2>/dev/null | grep -v '\.agent')" ]] && needs_compile=1
            else
                # Portable POSIX check replacing GNU-only find -quit
                [[ -n "$(find "$path" -maxdepth 3 -not -path '*/.git/*' -not -path '*/.agent/*' -not -name '*.md' -newer "$map" -print 2>/dev/null | head -n 1)" ]] && needs_compile=1
            fi

            if [[ "$needs_compile" -eq 1 ]]; then
                "$_AI_PY" "$_AI_DIR/tools/index-map/index-map" --agent "$path" || { rm -f "$lockfile"; return 1; }
            fi
        fi

        AI_ACTIVE_SKILL="${skills[*]}" AI_WORKSPACE_PATH="$path" "$_AI_PY" "$_AI_DIR/ai-agent.py" --talk-chat
        _ai_teleport
        rm -f "$lockfile" 2>/dev/null
    else
        "$_AI_PY" "$_AI_DIR/ai-agent.py" --talk "$@"
    fi
}

# 6. Terminal Markdown Pager
view() {
    local f="${1:-}"
    if [[ -z "$f" ]]; then
        if [ ! -t 0 ]; then
            FORCE_COLOR=1 "$_AI_PY" -c "import sys,rich.markdown,rich.console;rich.console.Console().print(rich.markdown.Markdown(sys.stdin.read()))"
        else
            echo "Usage: view <file.md> or <command> | view" >&2
            return 1
        fi
    elif [[ "$f" == *.md && -f "$f" ]]; then
        FORCE_COLOR=1 "$_AI_PY" -m rich.markdown "$f"
    elif [[ -f "$f" ]]; then
        cat "$f"
    else
        echo "view: file not found: $f" >&2
        return 1
    fi
}
