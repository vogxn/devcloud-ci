#!/bin/bash

getNext() {
    if [ -z `vboxmanage list runningvms`]; then
        local next=$(vboxmanage list vms | head -1 | awk '{print $1}')
    else
        local next=$(vboxmanage list vms | grep -vE "`vboxmanage list runningvms`" | head -1 | awk '{print $1}')
    fi

    if [ -n $next ]; then
        echo $next | sed 's/"//g'
    else
        echo "Out of capacity. All workers busy"
        exit 4
    fi
}

startVm() {
    if  [ -n $1 ]; then
        worker=$1
        vboxmanage startvm $1 --type headless
        return $?
    fi
}

stopVm() {
    if  [ -n $1 ]; then
        vboxmanage controlvm $1 poweroff
        return $?
    fi
}

startVm $(getNext)
#After returns nosetests-gitcommit.xml
#stopVm $worker
