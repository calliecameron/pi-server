



check-path '@@@@@1@@@@@'

if ! mount | grep '@@@@@2@@@@@' &>/dev/null; then
    mount '@@@@@2@@@@@'
fi
check-path '@@@@@2@@@@@'
umount '@@@@@2@@@@@'
