#!/usr/bin/python -u
# A script to provision node via Duffy API and run centos testsuite
# Author: Athmane Madjoudj <athmane@fedoraproject.org>
#

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib



BASE_URL = "http://admin.ci.centos.org:8080"
API_KEY = os.environ['APIKEY']

NODE_TYPE = {
    "c7_64" : {"arch":"x86_64", "ver":"7"},
    "c6_64" : {"arch":"x86_64", "ver":"6"},
    "c6_32" : {"arch":"i386", "ver":"6"},
    "c5_64" : {"arch":"x86_64", "ver":"5"},
    "c5_32" : {"arch":"i386", "ver":"5"},

}

def test_port(address, port):
    s = socket.socket()
    try:
        s.connect((address, port))
        return True
    except socket.error:
        return False


class CentOSCI:
    def __init__(self):
        pass
    def create_vm(self,vm_tmpl):
        get_node_url = "%s/Node/get?key=%s&ver=%s&arch=%s" % (BASE_URL, API_KEY, NODE_TYPE[vm_tmpl]["ver"], NODE_TYPE[vm_tmpl]["arch"])
        get_node_result = json.loads(urllib.urlopen(get_node_url).read())
        return (get_node_result['ssid'], get_node_result['hosts'][0])
        
    def ssh_run(self, ip_addr, cmd):
        return  subprocess.call("ssh -o StrictHostKeyChecking=no root@%s '%s'" % (ip_addr,cmd), shell=True)

    def scp_jenkins_workspace(self, ip_addr):
        return  subprocess.call("scp -r -o StrictHostKeyChecking=no %s root@%s:/root/ " % (os.environ['WORKSPACE'], ip_addr), shell=True)

    def terminate_vm(self, vm_id):
        terminate_node_url = "%s/Node/done?key=%s&ssid=%s" % (BASE_URL, API_KEY, vm_id)
        return urllib.urlopen(terminate_node_url).read()
    
if __name__ == '__main__':
    vm_type = sys.argv[1]
    
    if vm_type in NODE_TYPE.keys():
        ci = CentOSCI()

        vm_id, vm_ip = ci.create_vm(vm_tmpl = vm_type)
        # SIGTERM handler [THIS IS UGLY]
        def sigterm_handler(signal, frame):
            print "Build terminated ..."
            ci.terminate_vm(vm_id)
            sys.exit(1)
        signal.signal(signal.SIGTERM, sigterm_handler)

        print 'Waiting for SSHD on %s ...' % (vm_ip,)
        timeout = time.time() + 60*40 # 20mn
        while True:
            time.sleep(30)
            if test_port(vm_ip, 22) or time.time() > timeout:
                break
        testsuite_cmds = [ 'cd /root/%s && chmod +x ./centos_ci_build && ./centos_ci_build' % os.path.basename(os.environ['WORKSPACE'])]
        out = 0
        try:
            print 'Copying the test suite ...'
            ci.scp_jenkins_workspace(vm_ip)
            print 'Running the test suite ...'
            for testsuite_cmd in testsuite_cmds:
                out = ci.ssh_run(ip_addr = vm_ip, cmd = testsuite_cmd)

        except Exception, e:
            print "Can't connect to the VM: %s" % str(e)

        finally:
            try:
                print "Terminating the VM ..."
                ci.terminate_vm(vm_id)
            except Exception, e2:
                print "Can't terminate the VM: %s" % str(e2)
        sys.exit(out)

    else:
        print 'Invalid VM type.'
        sys.exit(1)
