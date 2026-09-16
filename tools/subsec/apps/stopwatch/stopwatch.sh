#!/usr/bin/env bash
# Minimalist Pure Bash High-Resolution Stopwatch v2.0
# Features: Spacebar Stop/Resume, Multi-Stop (Split) Logging, and Reset

cleanup() {
    # Restore cursor, re-enable echo/canonical mode, and clean line
    echo -ne "\033[?25h"
    stty echo icanon 2>/dev/null || true
    echo -ne "\r\033[K"
    exit 0
}
trap cleanup INT TERM EXIT

# Hide cursor
echo -ne "\033[?25l"

# Convert an integer of hundredths of a second into HH:MM:SS.hh
fmt_time() {
    local t=$1
    local h=$(( t / 360000 ))
    local m=$(( (t / 6000) % 60 ))
    local s=$(( (t / 100) % 60 ))
    local cs=$(( t % 100 ))
    printf "%02d:%02d:%02d.%02d" $h $m $s $cs
}

# Convert signed hundredths delta into +MM:SS.hh / -MM:SS.hh
fmt_delta() {
    local d=$1
    local sign="+"
    if (( d < 0 )); then
        sign="-"
        d=$(( -d ))
    fi
    local m=$(( (d / 6000) % 60 ))
    local s=$(( (d / 100) % 60 ))
    local cs=$(( d % 100 ))
    printf "%s%02d:%02d.%02d" "$sign" $m $s $cs
}

# Fetch current timestamp as integer hundredths of a second
get_now_cs() {
    local now=$EPOCHREALTIME
    local now_s=${now%.*}
    local now_us=${now#*.}
    echo $(( 10#$now_s * 100 + 10#${now_us:0:2} ))
}

# Stopwatch State
is_running=1
accum_elapsed=0
start_t=$(get_now_cs)
stop_count=0
last_split_t=0

while true; do
    # 1. Calculate high-res elapsed time
    if (( is_running )); then
        now_t=$(get_now_cs)
        elapsed=$(( accum_elapsed + (now_t - start_t) ))
    else
        elapsed=$accum_elapsed
    fi

    time_str=$(fmt_time $elapsed)

    # 2. Render status line
    if (( is_running )); then
        printf "\r\033[K \033[1;42;30m RUNNING \033[0m \033[1m%s\033[0m  \033[90m[Space]Stop  [S/Enter]Split  [R]Reset  [Q]Quit\033[0m" "$time_str"
    else
        printf "\r\033[K \033[1;41;37m STOPPED \033[0m \033[1;33m%s\033[0m  \033[90m[Space]Resume  [S]Save Stop  [R]Reset  [Q]Quit\033[0m" "$time_str"
    fi

    # 3. Non-blocking key capture (serves as ~20 FPS sleep timer and input listener)
    if IFS= read -rsn1 -t 0.05 key; then
        case "$key" in
            ' ') # Spacebar -> Toggle Start / Stop
                if (( is_running )); then
                    now_t=$(get_now_cs)
                    accum_elapsed=$(( accum_elapsed + (now_t - start_t) ))
                    is_running=0
                else
                    start_t=$(get_now_cs)
                    is_running=1
                fi
                ;;

            s|S|l|L|"") # Multi-Stop / Split record (S, L, or Enter key)
                if (( elapsed > 0 )); then
                    stop_count=$(( stop_count + 1 ))
                    delta=$(( elapsed - last_split_t ))
                    last_split_t=$elapsed
                    delta_str=$(fmt_delta $delta)

                    # Print the recorded stop permanently into scrollback above the ticker
                    printf "\r\033[K \033[1;36m▶ STOP #%02d\033[0m  \033[1m%s\033[0m  \033[90m(Delta: %s)\033[0m\n" \
                        $stop_count "$time_str" "$delta_str"
                fi
                ;;

            r|R) # Reset timer back to 0
                accum_elapsed=0
                last_split_t=0
                stop_count=0
                start_t=$(get_now_cs)
                ;;

            q|Q) # Quit
                cleanup
                ;;

            $'\e') # Esc or escape sequence check
                read -rsn2 -t 0.01 trailing
                if [[ -z "$trailing" ]]; then
                    cleanup
                fi
                ;;
        esac
    fi
done
