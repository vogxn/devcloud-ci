echo $WORKSPACE
whoami

getNext() {
    if [ -z `vboxmanage list runningvms` ]; then
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

getStatus() {
    if [ -n $1 ]; then
        local s=$(vboxmanage list runningvms | grep $1 | wc -l)
        if [ $s -eq 1 ]; then
            echo "running"
        else
            echo "stopped"
        fi
    fi
}

startVm() {
    if  [ -n $1 ]; then
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



worker=$(getNext)
startVm $worker

timeout=1800
sleep $timeout

worker_status=$(getStatus $worker)
if [ $worker_status=="running" ];then
    vboxmanage controlvm $worker poweroff
    sleep 100
fi

snapshot=$(vboxmanage snapshot $worker list | awk '{print $4}' | sed 's/)//g')
vboxmanage snapshot $worker restore $snapshot

mkdir -p $WORKSPACE/reports
cp -r *.xml $WORKSPACE/reports/
