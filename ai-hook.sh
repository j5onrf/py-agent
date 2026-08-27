#!/usr/bin/env bash
# Production Py-Agent Shell Hook v0.9.9

[[ $- == *i* && -f "$HOME/.config/py-agent/ai-agent.py" ]] || return
_AI_DIR="$HOME/.config/py-agent"
_AI_PY=$(command -v python3 || command -v python)

_ai_teleport() {
    local f="$_AI_DIR/.active_cd.$$"
    [[ -f "$f" ]] && { cd "$(<"$f")" 2>/dev/null; rm -f "$f"; }
    for old in "$_AI_DIR"/.active_cd.*; do
        [[ -f "$old" ]] && { kill -0 "${old##*.active_cd.}" 2>/dev/null || rm -f "$old"; }
    done
}

if [[ -n "$ZSH_VERSION" ]]; then
    autoload -Uz add-zsh-hook 2>/dev/null && add-zsh-hook precmd _ai_teleport
elif [[ "$PROMPT_COMMAND" != *_ai_teleport* ]]; then
    PROMPT_COMMAND="_ai_teleport${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi

ai_handle_missing() {
    local cmd exp
    cmd=$([[ -n "$*" ]] && "$_AI_PY" "$_AI_DIR/ai-agent.py" --interactive "$*") || return 127
    exp=$(echo "$cmd" | sed -E 's/\x1b\[[0-9;]*[a-zA-Z]|\r//g') && exp="${exp//\~/$HOME}"
    [[ -d "$exp" ]] && ai init "$exp" || { [[ "$exp" == *.py ]] && "$_AI_PY" "$exp" || eval "$exp"; }
}
command_not_found_handle() { [[ "$1" != --* ]] && ai_handle_missing "$*"; }
command_not_found_handler() { command_not_found_handle "$@"; }

ai() {
    if [[ "$1" == "init" ]]; then
        local path skills=() name map db map_arg=()
        path=$(pwd)
        [[ -n "${2:-}" && "${2:-}" != -* ]] && { path="$2"; skills=("${@:3}"); } || skills=("${@:2}")
        mkdir -p "$path" && path=$(CDPATH= cd "$path" && pwd -P) || return 1
        echo "$path" > "$_AI_DIR/.active_cd.$$"
        name=$(basename "$path")

        if grep -q '"map": *true' "$path/.agent/config.json" 2>/dev/null; then
            map="$path/.agent/index-map-$name.txt"; [[ -f "$map" ]] || map="$path/index-map-$name.txt"
            db="$path/.agent/index-map-memory-$name.db"; [[ -f "$db" ]] || db="$path/index-map-memory-$name.db"

            if [[ ! -f "$map" || ! -f "$db" || "$path" -nt "$map" ]] || [[ -n "$(find "$path" -mindepth 1 -not -path '*/.git/*' -not -path '*/.agent/*' -not -name '*.md' -newer "$map" -print -quit 2>/dev/null)" ]]; then
                "$_AI_PY" "$_AI_DIR/tools/index-map/index-map" --agent "$path" || { rm -f "$_AI_DIR/.active_cd.$$"; return 1; }
                map="$path/.agent/index-map-$name.txt"; [[ -f "$map" ]] || map="$path/index-map-$name.txt"
            fi
            [[ -f "$map" ]] && map_arg=("$(<"$map")")
        fi

        AI_ACTIVE_SKILL="${skills[*]}" AI_WORKSPACE_PATH="$path" "$_AI_PY" "$_AI_DIR/ai-agent.py" --talk-chat "${map_arg[@]}"
        _ai_teleport
    else
        "$_AI_PY" "$_AI_DIR/ai-agent.py" --talk "$@"
    fi
}

view() {
    local f="${1:-}"
    if [[ -z "$f" && (! -t 0 || -p /dev/stdin) ]]; then
        FORCE_COLOR=1 "$_AI_PY" -c "import sys,rich.markdown,rich.console;rich.console.Console().print(rich.markdown.Markdown(sys.stdin.read()))"
    elif [[ -n "$f" && "$f" == *.md && -f "$f" ]]; then
        FORCE_COLOR=1 "$_AI_PY" -m rich.markdown "$f"
    elif [[ -n "$f" ]]; then
        cat "$@"
    else
        cat
    fi
}
