devcloud-ci
===========

Continuous integration tests running within devcloud workers


0. cleanup vmops.log, nosetests.xml and vm-uninstall all VMs
1. build marvin and apidoc
2. install marvin from 1. in to virtualenv, install marvin-nose
3. mvn deploydb
4. mvn jetty:run
5. mvn deploysvr
6. nosetests run - testSetupSuccess.py
7. nosetestes run -a tags='devcloud'
8. copy nosetests.xml.<sha1.id> back to host and then to jenkins @ builds.a.o
