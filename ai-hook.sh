#!/usr/bin/env bash
# Production Py-Agent Shell Hook (Sub-Millisecond Startup)

[[ $- == *i* && -f "$HOME/.config/py-agent/ai-agent.py" ]] || return 0 2>/dev/null || exit 0

_AI_DIR="$HOME/.config/py-agent"
_AI_PY="${_AI_PY:-/usr/bin/python3}"

# 1. Atomic Shell Teleportation (Builtin only, first-draw screen hygiene)
_ai_teleport() {
    if [[ -z "${_AI_FIRST_PROMPT:-}" ]]; then
        _AI_FIRST_PROMPT=1
        printf '\x1b[H\x1b[2J'
    fi

    local f="$_AI_DIR/.active_cd.$$"
    if [[ -f "$f" ]]; then
        local target=""
        IFS= read -r target < "$f" 2>/dev/null
        rm -f "$f"
        [[ -n "$target" && -d "$target" ]] && cd "$target" 2>/dev/null
    fi
}

# High-Performance Hook Registration (Zero-Fork Bash & Zsh)
if [[ -n "$BASH_VERSION" ]]; then
    if (( BASH_VERSINFO[0] >= 5 )); then
        if [[ ${PROMPT_COMMAND@a} == *a* ]]; then
            case " ${PROMPT_COMMAND[*]} " in
                *" _ai_teleport "*) ;;
                *) PROMPT_COMMAND+=(_ai_teleport) ;;
            esac
        else
            [[ "${PROMPT_COMMAND:-}" != *_ai_teleport* ]] && PROMPT_COMMAND="_ai_teleport${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
        fi
    else
        [[ "${PROMPT_COMMAND:-}" != *_ai_teleport* ]] && PROMPT_COMMAND="_ai_teleport${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
    fi
elif [[ -n "$ZSH_VERSION" ]]; then
    autoload -Uz add-zsh-hook 2>/dev/null && add-zsh-hook precmd _ai_teleport
fi

# 2. Intent & Missing Command Handler
ai_handle_missing() {
    local cmd exp
    [[ $# -gt 0 ]] || return 127
    cmd=$("$_AI_PY" "$_AI_DIR/ai-agent.py" --interactive "$@") || return 127
    [[ -z "$cmd" ]] && return 127

    exp=$(printf '%s' "$cmd" | sed -E $'s/\x1b\\][^\x07\x1b]*(\x07|\x1b\\\\)|\x1b\\[[0-9;?]*[a-zA-Z~]|\r//g' | LC_ALL=C tr -d '\000-\010\013-\037\177')
    [[ -z "$exp" ]] && return 127

    _AI_HANDLED=1

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
        if [[ -n "$BASH_VERSION" ]]; then
            if ! bash -n <<< "$exp" 2>/dev/null; then
                echo "py-agent: invalid shell syntax in command" >&2
                return 127
            fi
        else
            if ! zsh -n <<< "$exp" 2>/dev/null; then
                echo "py-agent: invalid shell syntax in command" >&2
                return 127
            fi
        fi
        eval "$exp"
    fi
}

# 3. Command Not Found Hooks (Pure Built-in Chaining)
if [[ -n "$BASH_VERSION" ]]; then
    if [[ -z "${_AI_CNF_INSTALLED:-}" ]]; then
        _AI_CNF_INSTALLED=1
        if declare -F command_not_found_handle >/dev/null 2>&1; then
            _orig_def=$(declare -f command_not_found_handle)
            eval "_orig_cnf_handle() ${_orig_def#*$'\n'}"
            unset _orig_def
        fi
    fi
    command_not_found_handle() {
        [[ -n "${_AI_CNF_ACTIVE:-}" ]] && return 127
        [[ "${1:-}" != --* ]] || return 127
        local _AI_HANDLED=0 _AI_CNF_ACTIVE=1 cmd_rc=127
        ai_handle_missing "$@"
        cmd_rc=$?
        if [[ "$_AI_HANDLED" -eq 1 ]]; then
            return "$cmd_rc"
        fi
        if declare -F _orig_cnf_handle >/dev/null 2>&1; then
            _orig_cnf_handle "$@"
            return $?
        fi
        return 127
    }
elif [[ -n "$ZSH_VERSION" ]]; then
    if (( $+functions[command_not_found_handler] )) && [[ -z "${_orig_cnf_handler+x}" ]]; then
        functions[_orig_cnf_handler]=$functions[command_not_found_handler]
    fi
    command_not_found_handler() {
        [[ -n "${_AI_CNF_ACTIVE:-}" ]] && return 127
        [[ "${1:-}" != --* ]] || return 127
        local _AI_HANDLED=0 _AI_CNF_ACTIVE=1 cmd_rc=127
        ai_handle_missing "$@"
        cmd_rc=$?
        if [[ "$_AI_HANDLED" -eq 1 ]]; then
            return "$cmd_rc"
        fi
        if (( $+functions[_orig_cnf_handler] )); then
            _orig_cnf_handler "$@"
            return $?
        fi
        return 127
    }
fi

# 4. Primary AI Shell Wrapper
ai() {
    local old files=()
    if [[ -n "$BASH_VERSION" ]]; then
        local nullglob_set=0
        shopt -q nullglob && nullglob_set=1
        shopt -s nullglob
        files=("$_AI_DIR"/.active_cd.*)
        [[ "$nullglob_set" -eq 0 ]] && shopt -u nullglob
    else
        files=("$_AI_DIR"/.active_cd.*(N))
    fi

    for old in "${files[@]}"; do
        [[ -e "$old" ]] || continue
        local pid="${old##*.active_cd.}"
        if [[ "$pid" =~ ^[0-9]+$ ]]; then
            if ! kill -0 "$pid" 2>/dev/null; then
                rm -f "$old"
            else
                local comm
                comm=$(ps -p "$pid" -o comm= 2>/dev/null | tr -d ' -')
                if [[ -n "$comm" && ! "$comm" =~ (bash|zsh|sh)$ ]]; then
                    rm -f "$old"
                fi
            fi
        else
            rm -f "$old"
        fi
    done

    if [[ "${1:-}" == "init" ]]; then
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

        local _saved_traps
        _saved_traps=$(trap -p INT TERM 2>/dev/null)
        trap 'rm -f "'"$lockfile"'" 2>/dev/null; eval "${_saved_traps:-trap - INT TERM}"' INT TERM

        local cfg="$path/.agent/config.json"
        local use_map=0
        if [[ -f "$cfg" ]] && grep -qiE '"(map|use_map)"\s*:\s*(true|1)' "$cfg" 2>/dev/null; then
            use_map=1
        fi

        if [[ "$use_map" -eq 1 ]]; then
            map="$path/.agent/index-map-$name.txt"; [[ -f "$map" ]] || map="$path/index-map-$name.txt"
            db="$path/.agent/index-map-memory-$name.db"; [[ -f "$db" ]] || db="$path/index-map-memory-$name.db"

            if [[ ! -f "$map" || ! -f "$db" ]]; then
                "$_AI_PY" "$_AI_DIR/tools/index-map/index-map" --agent "$path" 2>/dev/null || true
            fi
        fi

        AI_ACTIVE_SKILL="${skills[*]}" AI_WORKSPACE_PATH="$path" "$_AI_PY" "$_AI_DIR/ai-agent.py" --talk-chat
        _ai_teleport
        rm -f "$lockfile" 2>/dev/null

        if [[ -n "$_saved_traps" ]]; then
            eval "$_saved_traps"
        else
            trap - INT TERM
        fi
    else
        "$_AI_PY" "$_AI_DIR/ai-agent.py" --talk "$@"
    fi
}

# 5. Terminal Markdown Pager (Unified Rich Engine)
aiview() {
    local f="${1:-}"
    if [[ -n "$f" && ! -f "$f" ]]; then
        echo "aiview: file not found: $f" >&2
        return 1
    fi

    if [[ -n "$f" && "$f" != *.md ]]; then
        cat "$f"
        return 0
    fi

    if [[ -z "$f" && -t 0 ]]; then
        echo "Usage: aiview <file.md> or <command> | aiview" >&2
        return 1
    fi

    FORCE_COLOR=1 "$_AI_PY" -c '
import sys
from rich.console import Console
from rich.markdown import Markdown

src = open(sys.argv[1], "r", encoding="utf-8", errors="replace").read() if len(sys.argv) > 1 else sys.stdin.read()
Console().print(Markdown(src, code_theme="monokai", justify="default"))
' "${f:+"$f"}"
}

if ! command -v view >/dev/null 2>&1; then
    alias view=aiview
fi
