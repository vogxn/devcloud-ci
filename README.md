devcloud-ci
===========

Apache CloudStack Continuous integration tests running within devcloud workers.
All code in this repo is licensed under ASLv2

The xcp-based [devcloud][1] is capable of deploying a basic zone cloudstack
environment. We've patched this appliance with a clone of the
[incubator-cloudstack][2] asf repo and our test utilities ([marvin][3], [cloudmonkey][4]) and
created a [*'testcloud'*][5]  appliance. The following workflow explains the
way tests are run within the appliance: 

Workflow
--------
The testcloud  appliance contains an init script at `/etc/init.d/devcloud` that
will start up a testrunner process when the appliance boots. Following this the
testrunner will perform the necessary setup to prepare a basic zone cloudstack
management server.  

1. The test runner fetches the latest HEAD (currently set to master) from the git repository and builds cloudstack.  In other words - `mvn install`
2. This is followed by an installation of marvin so we have the latest APIs available via the test framework
3. Further on the client inside a jetty:run will start up a management server process and have the API server listening for requests
4. We then configure this management server with the basic zone devcloud configuration with one XCP host and local storage. ie the config at `tools/devcloud/devcloud.cfg`
5. Once we have the basic zone running we will do a basic health check that verifies the following
    * All system VMs have come up and are successfully 'Running'
    * All the featured templates (built-in) are in Ready (downloaded) state
8. Iff the health check succeeds the environment is ready to run tests
9. nose's testrunner with the marvin plugin will collect all the tests marked with the attribute of 'devcloud'  `@attr(tags='devcloud')`, put them in a suite and run them
10. The nose xUnit plugin gives us the XML output for consumption into jenkins
11. Management Server log, logs from the test appliance's init script and the test results are posted to the machine hosting the 'testcloud' appliance and held as artifacts on the [jenkins job][6] for troubleshooting and held as artifacts on the jenkins job for troubleshooting
12. A jenkins slave agent within the host will send through the results and logs to the jenkins master at jenkins.c.o

Test Workers
--------
The host machine is a Ubuntu server with virtualbox 4.2 installed with guest
additions. VirtualBox does dhcp for the 'testcloud' workers that it spins up.
The testcloud image itself is cloned into multiple test workers (currently 5).
A simple scheduler will pick up an idle worker vm on trigger from jenkins
master that is polling for commits on the git:repo. Once picked up each worker
will perform all the tests and post the results back to the gateway/dhcp which
in our case is the host machine running virtualbox. A jenkins slave runs in
headless mode on the host machine and posts results back to jenkins master.

After the testworker has done its job and posted its results back to jenkins we
wait for a timeout (1800s) to release it back to the pool of workers. To clean
up the image of any remnants from the previous test run the worker is restored
to a base snapshot keeping the environment clean for the subsequent run.

[1]: https://cwiki.apache.org/confluence/display/CLOUDSTACK/devcloud "devcloud"
[2]: https://git-wip-us.apache.org/repos/asf?p=incubator-cloudstack.git "incubator-cloudstack"
[3]: https://cwiki.apache.org/confluence/display/CLOUDSTACK/Testing+with+Python "marvin"
[4]: https://cwiki.apache.org/confluence/display/CLOUDSTACK/CloudStack+cloudmonkey+CLI "cloudmonkey"
[5]: https://people.apache.org/~tsp/testcloud.ova "testcloud"
[6]: http://jenkins.cloudstack.org/view/debug/job/testcloud-master-basic/ "jenkins.cs.o"
