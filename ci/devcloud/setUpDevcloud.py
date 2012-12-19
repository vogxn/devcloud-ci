#/usr/bin/env python
from ci.devcloud.bashUtils import bash
from os import chdir
from os import path
from ci.devcloud.bashUtils import NetUtils

TEST_HOME = '/opt/cloudstack/incubator-cloudstack'
SED_DFLTIP1 = ''.join(['\/', '192.168.56.10', '\/'])
SED_DFLTIP2 = ''.join(['\/', '192.168.56.10', ':'])
SED_XENBR01 = ''.join(['\/', str(NetUtils.getIpAddress('xenbr0')), '\/'])
SED_XENBR02 = ''.join(['\/', str(NetUtils.getIpAddress('xenbr0')), ':'])
MARVIN_CFG = path.join(TEST_HOME, 'tools/devcloud/devcloud.cfg')

def cleanUp():
    chdir(TEST_HOME)
    #kill any running java
    bash("killall -9 java")

    #cleanup installed VMs
    bash("xe vm-uninstall --force --multiple")
    #TODO:cleanup secondary storage?

    #cleanup logs
    chdir(TEST_HOME)
    bash("cat /dev/null > vmops.log")

def removeMarvin():
    #uninstall marvin, marvin-nose
    bash("pip uninstall -y marvin-nose")
    bash("pip uninstall -y marvin")

def buildMarvin():
    chdir(TEST_HOME)
    bash("mvn -P developer -pl :cloud-apidoc -pl :cloud-marvin")

def installMarvin():
    chdir(TEST_HOME)
    install_path = path.join(TEST_HOME, "tools/marvin/dist/Marvin-0.1.0.tar.gz")
    if path.exists(install_path):
        bash("pip install %s"%install_path)

    marvin_nose_path = path.join(TEST_HOME, "tools/marvin/marvin")
    chdir(marvin_nose_path)
    bash("pip install .")

def startManagement():
    chdir(TEST_HOME)
    bash("mvn -P developer -pl :cloud-client-ui jetty:run &", background=True)
    bash("sleep 60") #TODO: Figure out working with listCapabilities

def configure():
    chdir(TEST_HOME)
    if path.exists(MARVIN_CFG):
        #reset tools/devcloud.cfg with testworkers' ip settings
        bash("sed -iv 's/%s/%s/g' %s"%(SED_DFLTIP1, SED_XENBR01, MARVIN_CFG))
        bash("sed -iv 's/%s/%s/g' %s"%(SED_DFLTIP2, SED_XENBR02, MARVIN_CFG))
    else:
        raise Exception("marvin configuration not found")
    bash("mvn -P developer -pl tools/devcloud -Ddeploysvr")

def buildCloudStack():
    chdir(TEST_HOME)
    bash("mvn -P developer,systemvm clean install -DskipTests")
    bash("mvn -P developer -pl developer,tools/devcloud -Ddeploydb")

def healthCheck():
    chdir(TEST_HOME)
    return bash("nosetests -v --with-marvin --marvin-config=%s --load %s"%(MARVIN_CFG, "tools/marvin/marvin/testSetupSuccess.py"))

if __name__ == '__main__':
    #setup devcloud
    cleanUp()
    removeMarvin()
    buildCloudStack()

    buildMarvin()
    installMarvin()

    startManagement()
    configure()
    bash("mysql -uroot -Dcloud -e\"update configuration set value='%s' where name='host'\""%NetUtils.getIpAddress('xenbr0'))
    cleanUp()
    startManagement()

    if healthCheck():
        bash("nosetests -v --with-marvin --marvin-config=%s -a tags='devcloud' --load %s"%(MARVIN_CFG, "test/integration/smoke/test_vm_life_cycle.py"))
    else:
        raise Exception("Health check fails!")