#/usr/bin/env python
import argparse
import string
from ci.devcloud.bashUtils import remoteSSHClient
from ci.devcloud.bashUtils import NetUtils

if __name__== '__main__':
    parser = argparse.ArgumentParser(description='Return ip and mac info to devcloud host')

    parser.add_argument('--host', action="store", dest="host", default='192.168.56.1')
    parser.add_argument('--user', action="store", dest="user", default='root')
    parser.add_argument('--pass', action="store", dest="passwd", default='password')
    parser.add_argument('--out', action="store", dest="out", default='~/vbox/dhcp')

    args = parser.parse_args()

    #Convert from 08:00:27:bd:08:a1 to 080027BD08A1
    worker_mac = NetUtils.getHwAddress('xenbr0')
    worker_mac = string.upper(worker_mac)
    worker_mac = ''.join(worker_mac.split(':'))

    worker_ip = NetUtils.getIpAddress('xenbr0')
    print worker_mac, worker_ip

    devcloud = remoteSSHClient.get_ssh_conn(args.host, 22, args.user, args.passwd)
    devcloud.execute("echo %s > %s/%s"%(worker_ip, args.out, worker_mac))

