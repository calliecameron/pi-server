# Common stuff; should be sourced, not run!


# Is this really a Pi, or is it a Debian VM for testing?
function real-pi()
{
    if [ "$(uname -m)" = 'armv6l' ]; then
        return 0
    else
        return 1
    fi
}

function enter-to-continue()
{
    read -p "Press ENTER to continue..."
}
