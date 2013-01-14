#/usr/bin/env python
import argparse
import zipfile
import logging
import string
from ci.devcloud.bashUtils import bash
from os import chdir
from os import curdir
from os import path
from ci.devcloud.bashUtils import NetUtils
from ci.devcloud.bashUtils import remoteSSHClient

class DevCloudReporter(object):
    def __init__(self, host='localhost', password='password', user='devcloud', outdir='~/vbox'):
        self.host = host
        self.password = password
        self.user = user
        self.outdir = outdir
        self.devcloud = remoteSSHClient(self.host, 22, self.user, self.password)

    def postNetworkInfo(self):
        #Convert from 08:00:27:bd:08:a1 to 080027BD08A1
        worker_mac = NetUtils.getHwAddress('xenbr0')
        worker_mac = string.upper(worker_mac)
        worker_mac = ''.join(worker_mac.split(':'))
        worker_ip = NetUtils.getIpAddress('xenbr0')
        self.devcloud.execute("echo %s > %s/%s" % (worker_ip, args.out, worker_mac))

    def copyFile(self, filename):
        if path.exists(filename):
            chdir(path.dirname(filename))
            self.devcloud.scp(path.basename(filename), path.join(self.outdir, path.basename(filename)))
        else:
            raise IOError("Invalid path to copy")


class TestWorker(object):
    def __init__(self):
        self.TEST_HOME = '/opt/cloudstack/incubator-cloudstack'
        self.SED_DFLTIP1 = ''.join(['\/', '192.168.56.10', '\/'])
        self.SED_DFLTIP2 = ''.join(['\/', '192.168.56.10', ':'])
        self.SED_XENBR01 = ''.join(['\/', str(NetUtils.getIpAddress('xenbr0')), '\/'])
        self.SED_XENBR02 = ''.join(['\/', str(NetUtils.getIpAddress('xenbr0')), ':'])
        self.MARVIN_CFG = path.join(self.TEST_HOME, 'tools/devcloud/devcloud.cfg')
        self.resultXml = None

    def cleanUp(self):
        chdir(self.TEST_HOME)
        #kill any running java
        bash("killall -9 java")

        #cleanup installed VMs
        bash("xe vm-uninstall --force --multiple")
        #TODO:cleanup secondary storage?

        #cleanup logs
        chdir(self.TEST_HOME)
        bash("cat /dev/null > vmops.log")

    def installMarvin(self):
        chdir(self.TEST_HOME)
        install_path = path.join(self.TEST_HOME, "tools/marvin/dist/Marvin-0.1.0.tar.gz")
        if path.exists(install_path):
            bash("pip install %s"%install_path)

        marvin_nose_path = path.join(self.TEST_HOME, "tools/marvin/marvin")
        chdir(marvin_nose_path)
        bash("pip install .")

    def startManagement(self):
        chdir(self.TEST_HOME)
        bash("mvn -P developer -pl :cloud-client-ui jetty:run &", background=True)
        bash("sleep 60") #TODO: Figure out working with listCapabilities

    def configure(self):
        chdir(self.TEST_HOME)
        if path.exists(self.MARVIN_CFG):
            #reset tools/devcloud.cfg with testworkers' ip settings
            bash("sed -iv 's/%s/%s/g' %s"%(self.SED_DFLTIP1, self.SED_XENBR01, self.MARVIN_CFG))
            bash("sed -iv 's/%s/%s/g' %s"%(self.SED_DFLTIP2, self.SED_XENBR02, self.MARVIN_CFG))
        else:
            raise Exception("marvin configuration not found")
        bash("mvn -P developer -pl tools/devcloud -Ddeploysvr")

    def fastForwardRepo(self, commit_id='HEAD'):
        bash("git fetch origin %s"%commit_id)
        bash("git reset --hard FETCH_HEAD")
        return bash("git log -1 --pretty=oneline | awk '{print $1}'").getStdout()

    def buildCloudStack(self):
        chdir(self.TEST_HOME)
        bash("mvn -P developer,systemvm clean install -DskipTests")
        bash("mvn -P developer -pl developer,tools/devcloud -Ddeploydb")

    def healthCheck(self):
        chdir(self.TEST_HOME)
        return bash("nosetests -v --with-marvin --marvin-config=%s \
                --load %s"%(self.MARVIN_CFG, "tools/marvin/marvin/testSetupSuccess.py")).isSuccess()

    def runTests(self, repo_head):
        chdir(self.TEST_HOME)
        if self.healthCheck():
            result=bash("nosetests -v --with-xunit --xunit-file=%s.xml --with-marvin --marvin-config=%s -a tags='devcloud' "
                        "--load %s"%(repo_head, self.MARVIN_CFG, "test/integration/smoke/test_vm_life_cycle.py"))
            if result.isSuccess():
                self.resultXml = path.join(path.abspath(curdir), repo_head+'.xml')
                logging.info("SUCCESS")
            else:
                logging.info("FAIL")
        else:
            logging.error("Health Check Failure")
            raise Exception("Health check fails!")

    def getResultXml(self):
        if self.resultXml is not None:
            return self.resultXml


def run(worker, install_marvin):
    worker.cleanUp()
    repo_head = worker.fastForwardRepo()
    worker.buildCloudStack()

    if install_marvin:
        logging.debug("Installing marvin")
        worker.installMarvin()

    worker.startManagement()
    worker.configure()

    #FIXME: override/db.properties should be able to update the host
    bash("mysql -uroot -Dcloud -e\"update configuration set value='%s' where "
         "name='host'\""%NetUtils.getIpAddress('xenbr0'))

    worker.cleanUp()
    worker.startManagement()
    worker.runTests(repo_head)
    return worker.getResultXml()


def initLogging(logFile=None, lvl=logging.INFO):
    try:
        if logFile is None:
            logging.basicConfig(level=lvl, \
                                format="'%(asctime)-6s: %(name)s \
                                (%(threadName)s) - %(levelname)s - %(message)s'")
        else:
            logging.basicConfig(filename=logFile, level=lvl, \
                                format="'%(asctime)-6s: %(name)s \
                                (%(threadName)s) - %(levelname)s - %(message)s'")
    except:
        logging.basicConfig(level=lvl)


if __name__ == '__main__':
    testworkerlog="/var/log/devcloudworker.log"
    arch_name = "testworkerlog.zip"

    mslogs = ["/opt/cloudstack/incubator-cloudstack/vmops.log", "/opt/cloudstack/incubator-cloudstack/api.log"]
    arch_mgmt = "mslog.zip"
    initLogging(logFile=testworkerlog, lvl=logging.DEBUG)

    parser = argparse.ArgumentParser(description='Test worker')

    parser.add_argument('--host', action="store", dest="host", default='192.168.56.1')
    parser.add_argument('--user', action="store", dest="user", default='root')
    parser.add_argument('--pass', action="store", dest="passwd", default='password')
    parser.add_argument('--out', action="store", dest="out", default='~/vbox/dhcp')
    parser.add_argument('--marvin', action="store_true", dest="marvin", default=True)

    args = parser.parse_args()
    resultXml = run(TestWorker(), args.marvin)
    logging.info("test run recorded at %s"%resultXml)

    reporter = DevCloudReporter(args.host, args.passwd, args.user, args.out)
    logging.info("Posting network information about worker to gateway")
    reporter.postNetworkInfo()

    with zipfile.ZipFile(arch_name, "w") as zf:
        compression = zipfile.ZIP_DEFLATED
        zf.write(testworkerlog, compress_type=compression)

    with zipfile.ZipFile(arch_mgmt, "w") as mzf:
        compression = zipfile.ZIP_DEFLATED
        [mzf.write(log, compress_type=compression) for log in mslogs]

    [reporter.copyFile(f) for f in [resultXml, arch_name, arch_mgmt]]
    logging.info("copied test results and debug logs to gateway")
