#!/usr/bin/env bash
# Minimalist Pure Bash High-Resolution Stopwatch

cleanup() {
    echo -ne "\033[?25h" # Restore cursor
    echo -ne "\r\033[K"   # Wipe the stopwatch line cleanly
    exit 0
}
trap cleanup INT TERM EXIT

echo -ne "\033[?25l" # Hide cursor

# Parse start time into seconds and tenths of a second
start=$EPOCHREALTIME
start_s=${start%.*}
start_ms=${start#*.}
start_t=$(( 10#$start_s * 10 + 10#${start_ms:0:1} ))

while true; do
    now=$EPOCHREALTIME
    now_s=${now%.*}
    now_ms=${now#*.}
    now_t=$(( 10#$now_s * 10 + 10#${now_ms:0:1} ))

    # Calculate elapsed tenths of a second
    elapsed=$(( now_t - start_t ))

    tenths=$(( elapsed % 10 ))
    seconds=$(( (elapsed / 10) % 60 ))
    minutes=$(( (elapsed / 600) % 60 ))
    hours=$(( elapsed / 36000 ))

    # Render inline using your media controller's styling
    printf "\r \033[1;44;30m ELAPSED \033[0m \033[1m%02d:%02d:%02d.%d\033[0m" \
        $hours $minutes $seconds $tenths

    sleep 0.1
done
