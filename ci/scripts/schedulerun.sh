# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

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
