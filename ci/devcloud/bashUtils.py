from signal import alarm, signal, SIGALRM, SIGKILL
from subprocess import PIPE, Popen, list2cmdline
from time import sleep as delay
import logging
import threading
import telnetlib
import os
import sys
import time
import paramiko
import select
import socket
import fcntl
import struct
import Queue

class remoteSSHClient(object):
    def __init__(self, host, port, user, passwd):
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.ssh.connect(str(host), int(port), user, passwd)
        except paramiko.SSHException, sshex:
            logging.debug(repr(sshex))

    def execute(self, command):
        stdin, stdout, stderr = self.ssh.exec_command(command)
        output = stdout.readlines()
        errors = stderr.readlines()
        results = []
        if output is not None and len(output) == 0:
            if errors is not None and len(errors) > 0:
                for error in errors:
                    results.append(error.rstrip())

        else:
            for strOut in output:
                results.append(strOut.rstrip())

        return results

    def execute_buffered(self, command, bufsize=512):
        transport = self.ssh.get_transport()
        channel = transport.open_session()
        try:
            stdin, stdout, sterr = channel.exec_command(command)
            while True:
                rl, wl, xl = select.select([channel], [], [], 0.0)
                if len(rl) > 0:
                    logging.debug(channel.recv(bufsize))
        except paramiko.SSHException, e:
            logging.debug(repr(e))

    def scp(self, srcFile, destPath):
        transport = paramiko.Transport((self.host, int(self.port)))
        transport.connect(username=self.user, password=self.passwd)
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.put(srcFile, destPath)
        except IOError, e:
            raise e


class bash:
    def __init__(self, args, timeout=600, background=False):
        self.args = args
        logging.debug("execute:%s" % args)
        self.timeout = timeout
        self.process = None
        self.success = False
        self.background = background
        self.run()

    def run(self):
        class Alarm(Exception):
            pass

        def alarm_handler(signum, frame):
            raise Alarm

        try:
            if self.background:
                self.process = Popen(self.args, shell=True)
            else:
                self.process = Popen(self.args, shell=True, stdout=PIPE, stderr=PIPE)
            if self.timeout != -1:
                signal(SIGALRM, alarm_handler)
                alarm(self.timeout)

            try:
                self.stdout, self.stderr = self.process.communicate()
                if self.timeout != -1:
                    alarm(0)
            except Alarm:
                os.kill(self.process.pid, SIGKILL)

            self.success = self.process.returncode == 0
        except Exception as e:
            logging.error("encountered error %s when processing %s"%(e, self.args))

        if not self.success:
            logging.debug("Failed to execute:" + self.getErrMsg())


    def exec_commands(self, cmds):
        if not cmds: return # empty list

        def done(p):
            return p.poll() is not None
        def success(p):
            return p.returncode == 0
        def fail():
            sys.exit(1)

        max_task = 2
        processes = []
        while True:
            while cmds and len(processes) < max_task:
                task = cmds.pop()
                logging.debug(list2cmdline(task))
                processes.append(Popen(task))

            for p in processes:
                if done(p):
                    if success(p):
                        processes.remove(p)
                    else:
                        fail()

            if not processes and not cmds:
                break
            else:
                time.sleep(0.05)

    def isSuccess(self):
        return self.success

    def getStdout(self):
        try:
            return self.stdout.strip("\n")
        except AttributeError:
            return ""

    def getLines(self):
        return self.stdout.split("\n")

    def getStderr(self):
        try:
            return self.stderr.strip("\n")
        except AttributeError:
            return ""

    def getErrMsg(self):
        if self.isSuccess():
            return ""

        if self.getStderr() is None or self.getStderr() == "":
            return self.getStdout()
        else:
            return self.getStderr()


class NetUtils(object):
    """
    Simple network utilities
    """
    @staticmethod
    def isPortListening(host, port, timeout=120):
        """
        Scans 'host' for a listening service on 'port'
        """
        tn = None
        while timeout != 0:
            try:
                tn = telnetlib.Telnet(host, port, timeout=timeout)
                timeout = 0
            except Exception, e:
                logging.debug("Failed to telnet connect to %s:%s with %s" % (host, port, e))
                delay(5)
                timeout = timeout - 5
        if tn is None:
            logging.error("No service listening on port %s:%d" % (host, port))
            return False
        else:
            logging.info("Unrecognizable service up on %s:%d" % (host, port))
            return True

    @staticmethod
    def isPortOpen(host, port=22):
        """
        Checks if there is an open socket on specified port. Default is SSH
        """
        while True:
            channel = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            channel.settimeout(20)
            try:
                logging.debug("Attempting port=%s connect to host %s" % (port, host))
                err = channel.connect_ex((host, port))
            except socket.error, e:
                logging.debug("encountered %s retrying in 5s" % e)
                delay(5)
            finally:
                if err == 0:
                    logging.info("host: %s is ready" % host)
                    break
                else:
                    logging.debug("[%s] host %s is not ready. Retrying" % (err, host))
                    delay(5)
                    channel.close()

    @staticmethod
    def getIpAddress(ifname):
        """
        get IP address assigned to interface ifname
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15])
        )[20:24])


    @staticmethod
    def getHwAddress(ifname):
        """
        get hw address/MAC id of the interface ifname
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
        return ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1]


    @staticmethod
    def waitForHostReady(hostlist):
        """
        Wait for the ssh ports to open on the list of hosts in hostlist
        """
        logging.info("Waiting for hosts %s to refresh" % hostlist)
        hostQueue = Queue.Queue()

        for host in hostlist:
            t = threading.Thread(name='HostWait-%s' % hostlist.index(host), target=NetUtils.isPortOpen,
                args=(hostQueue, ))
            t.setDaemon(True)
            t.start()

        [hostQueue.put(host) for host in hostlist]
        hostQueue.join()
        logging.info("All hosts %s are up" % hostlist)