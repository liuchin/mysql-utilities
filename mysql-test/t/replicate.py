#!/usr/bin/env python

import os
import mutlib
from mysql.utilities.exception import MySQLUtilError, MUTException

class test(mutlib.System_test):
    """setup replication
    This test executes a simple replication setup among two servers.
    """

    def check_prerequisites(self):
        return self.check_num_servers(1)

    def setup(self):
        self.server0 = self.servers.get_server(0)
        self.server1 = None
        self.server2 = None
        self.s1_serverid = None
        self.s2_serverid = None

        index = self.servers.find_server_by_name("rep_slave")
        if index >= 0:
            self.server1 = self.servers.get_server(index)
            try:
                res = self.server1.show_server_variable("server_id")
            except MySQLUtilError, e:
                raise MUTException("Cannot get replication slave " +
                                   "server_id: %s" % e.errmsg)
            self.s1_serverid = int(res[0][1])
        else:
            self.s1_serverid = self.servers.get_next_id()
            res = self.servers.spawn_new_server(self.server0, self.s1_serverid,
                                               "rep_slave", ' --mysqld='
                                                '"--log-bin=mysql-bin "')
            if not res:
                raise MUTException("Cannot spawn replication slave server.")
            self.server1 = res[0]
            self.servers.add_new_server(self.server1, True)

        index = self.servers.find_server_by_name("rep_master")
        if index >= 0:
            self.server2 = self.servers.get_server(index)
            try:
                res = self.server2.show_server_variable("server_id")
            except MySQLUtilError, e:
                raise MUTException("Cannot get replication master " +
                                   "server_id: %s" % e.errmsg)
            self.s2_serverid = int(res[0][1])
        else:
            self.s2_serverid = self.servers.get_next_id()
            res = self.servers.spawn_new_server(self.server0, self.s2_serverid,
                                                "rep_master", ' --mysqld='
                                                '"--log-bin=mysql-bin "')
            if not res:
                raise MUTException("Cannot spawn replication slave server.")
            self.server2 = res[0]
            self.servers.add_new_server(self.server2, True)
            
        return True
    
    def run_test_case(self, slave, master, s_id,
                      comment, options=None, save_for_compare=False,
                      expected_result=0):

        master_str = "--master=%s" % self.build_connection_string(master)
        slave_str = " --slave=%s" % self.build_connection_string(slave)
        conn_str = master_str + slave_str
        
        # Test case 1 - setup replication among two servers
        if not save_for_compare:
            self.results.append(comment)
        cmd = "mysqlreplicate.py --rpl-user=rpl:rpl %s" % conn_str
        if options:
            cmd += " %s" % options
        if not save_for_compare:
            self.results.append(cmd)
        res = self.exec_util(cmd, self.res_fname)
        if not save_for_compare:
            self.results.append(res)
        
        if res != expected_result:
            return False

        # Now test the result and record the action.
        try:
            res = slave.exec_query("SHOW SLAVE STATUS")
            if not save_for_compare:
                self.results.append(res)
        except MySQLUtilError, e:
            raise MUTException("Cannot show slave status: %s" % e.errmsg)

        if save_for_compare:
            self.results.append(comment+"\n")
            for line in open(self.res_fname).readlines():
                # Don't save lines that have [Warning]
                index = line.find("[Warning]")
                if index <= 0:
                    self.results.append(line)

        return True
    
    def run(self):
        self.res_fname = "result.txt"
        
        comment = "Test case 1 - replicate server1 as slave of server2 "
        res = self.run_test_case(self.server1, self.server2, self.s1_serverid,
                                 comment, None)
        if not res:
            raise MUTException("%s: failed" % comment)
        
        try:
            res = self.server1.exec_query("STOP SLAVE")
        except:
            raise MUTException("%s: Failed to stop slave." % comment)

        comment = "Test case 2 - replicate server2 as slave of server1 "
        res = self.run_test_case(self.server2, self.server1, self.s2_serverid,
                                 comment, None)
        if not res:
            raise MUTException("%s: failed" % comment)
        
        try:
            res = self.server2.exec_query("STOP SLAVE")
        except:
            raise MUTException("%s: Failed to stop slave." % comment)

        return True

    def check_test_case(self, index, comment):
        msg = None
        test_passed = True
        
        # Check test case
        if self.results[index] == 0:
            if self.results[index+1] == ():
                return (false, "%s: Slave status missing." % comment)
            test_result = self.results[index+1][0]
            if test_result[0] != "Waiting for master to send event":
                test_passed = False
                msg = "%s: Slave failed to communicate with master." % comment
        else:
            test_passed = False
            msg = "%s: Replication event failed." % comment
        return (test_passed, msg)

    def get_result(self):
        # tc1 tc2 content
        # --- --- -----
        #  0   4  comment
        #  1   5  command
        #  2   6  result of exec_util
        #  3   7  result of SHOW SLAVE STATUS
        
        res = self.check_test_case(2, "Test case 1")
        if not res[0]:
            return res

        res = self.check_test_case(6, "Test case 2")
        if not res[0]:
            return res

        return (True, None)
        
    def mask_results(self):
        self.mask_column_result("| builtin", "|", 2, " XXXXXXXX ")
        self.mask_column_result("| XXXXXXX", "|", 3, " XXXXXXXXXXXXXXX ")
        self.mask_column_result("| XXXXXXX", "|", 4, " XXXXXXXXXXXXXXXXXXXX ")
        
        self.replace_result("#  slave id =", "#  slave id = XXX\n")
        self.replace_result("# master id =", "# master id = XXX\n")
        
        self.remove_result("# Creating replication user...")
        self.remove_result("CREATE USER 'rpl'@'localhost'")
        self.remove_result("# Granting replication access")
        self.remove_result("# CHANGE MASTER TO MASTER_HOST = 'localhost'")
    
    def record(self):
        # Not a comparative test, returning True
        return True
    
    def cleanup(self):
        if self.res_fname:
            os.unlink(self.res_fname)
        return True
