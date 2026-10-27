#!/usr/bin/env bash
# Small wifi menu for waybar (left click on the network module).
# Replaces the context menu of nm-applet.

source "$HOME/.config/waybar/scripts/menu-lib.sh"
menu_toggle_guard wifi
menu_x=$(menu_xoffset 360)

menu() {
    wofi --dmenu \
        --style "$HOME/.config/wofi/style.css" \
        --width 360 \
        --location top_left --xoffset "$menu_x" --yoffset 10 \
        "$@"
}

# Connects in the background and reports the result as a notification.
# Aufruf: run "Erfolgsmeldung" befehl arg...
run() {
    setsid -f bash -c '
        if out=$("${@:2}" 2>&1); then
            notify-send -a WLAN "WLAN" "$1"
        else
            notify-send -a WLAN -u critical "Wi-Fi error" "$out"
        fi' _ "$@" >/dev/null 2>&1
}

entries=()
declare -A actions ssids secured

if [[ $(nmcli radio wifi) == "enabled" ]]; then
    label="󰤭  turn wi-fi off"
    entries+=("$label")
    actions[$label]="toggle-off"

    # determine the connected network beforehand (several access points can share the same SSID)
    current=$(nmcli -t --escape no -f IN-USE,SSID dev wifi list --rescan no | sed -n 's/^\*://p' | head -n1)

    declare -A seen
    while IFS=: read -r _ signal security ssid; do
        [[ -z $ssid || -n ${seen[$ssid]} ]] && continue
        seen[$ssid]=1

        if   (( signal >= 80 )); then icon="󰤨"
        elif (( signal >= 60 )); then icon="󰤥"
        elif (( signal >= 40 )); then icon="󰤢"
        elif (( signal >= 20 )); then icon="󰤟"
        else                          icon="󰤯"
        fi
        lock=""
        [[ -n $security && $security != "--" ]] && lock=" 󰌾"

        if [[ $ssid == "$current" ]]; then
            label="$icon  $ssid$lock  · connected – disconnect"
            actions[$label]="disconnect"
        else
            label="$icon  $ssid$lock"
            actions[$label]="connect"
            [[ -n $lock ]] && secured[$label]=1
        fi
        ssids[$label]=$ssid
        entries+=("$label")
    done < <(nmcli -t --escape no -f IN-USE,SIGNAL,SECURITY,SSID dev wifi list --rescan no)

    # show the list immediately from the cache, rescan in the background for the next open
    setsid -f nmcli device wifi rescan >/dev/null 2>&1
else
    label="󰤨  turn wi-fi on"
    entries+=("$label")
    actions[$label]="toggle-on"
fi

label="󰒓  network settings …"
entries+=("$label")
actions[$label]="settings"

lines=$(( ${#entries[@]} + 1 ))
(( lines > 12 )) && lines=12
choice=$(printf '%s\n' "${entries[@]}" | menu --prompt "wi-fi" --lines "$lines")

[[ -n $choice && -n ${actions[$choice]} ]] || exit 0
ssid=${ssids[$choice]}

case ${actions[$choice]} in
    toggle-off) nmcli radio wifi off ;;
    toggle-on)  nmcli radio wifi on ;;
    settings)   setsid -f ~/.local/bin/rice-netz >/dev/null 2>&1 ;;
    disconnect)
        dev=$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1; exit}')
        run "Getrennt von $ssid" nmcli device disconnect "$dev"
        ;;
    connect)
        if nmcli -t -f NAME connection show | grep -Fxq -- "$ssid"; then
            # saved network: the password is already stored
            run "Verbunden mit $ssid" nmcli connection up id "$ssid"
        elif [[ -n ${secured[$choice]} ]]; then
            pw=$(menu --password --prompt "password for $ssid" --lines 1 </dev/null)
            [[ -n $pw ]] || exit 0
            run "Verbunden mit $ssid" nmcli device wifi connect "$ssid" password "$pw"
        else
            run "Verbunden mit $ssid" nmcli device wifi connect "$ssid"
        fi
        ;;
esac
