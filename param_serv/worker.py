#!/usr/bin/env python2
""" Client worker. """
from __future__ import print_function, with_statement, division, generators
import socket, json, struct
import threading
import sys, os, re, argparse, copy, time, datetime
import errno
from traceback import print_exc

from param_serv.headers import *
from param_serv.param_utils import *

class ConnectorThread(threading.Thread):
    """ This is the client worker thread; it's the object
    that sends and receives the data to and form the server """
    def __init__(
        self,
        meta,
        meta_rlock,
        db,
        db_rlock,
        server_ip,
        server_port
        ):

        super(self.__class__, self).__init__()
        
        self.conn = None
        self.meta = meta
        self.meta_rlock = meta_rlock
        self.db = db
        self.db_rlock = db_rlock
        self.server_ip = server_ip
        self.server_port = server_port

    def send_param(self, name, alpha, beta):
        """ Send parameter to server """
        try:
            with self.db[name] as tensor:
                # this action copies the data
                numeric_data = tensor.tobytes("C")
                type_string = str(tensor.ndtype)

        except KeyError, err:
            print("send_param error :: param of name '{param_name}' doesn't exist. The thread is not crashing." \
                .format(param_name=name))
            print_exc()
            return

        json_txt = json.dumps({
            "query_name": "send_param",
            "param_name": name,
            "alpha": alpha,
            "beta": beta,
            "ndtype": type_string
            })

        try:
            self.conn.sendall(struct.pack("iis", HEADER_JSON, len(json_txt), json_txt))
            self.conn.sendall(struct.pack("ii", HEADER_NUMERIC, len(numeric_data)) + numeric_data)

        except Exception, err:
            print("send_param error :: conn.sendall failed. The thread is not crashing.")
            print_exc()
            return
    
    def pull_full_param(self, name):
        """ Pull full parameter from server """                           

        json_txt = json.dumps({
            "query_name": "pull_full_param",
            "param_name": name,
            })

        try:
            self.conn.sendall(struct.pack("iis", HEADER_JSON, len(json_txt), json_txt))

        except Exception, err:
            print("send_param error :: conn.sendall failed. The thread is not crashing.")
            print_exc()
            return

    def run(self):

        #s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("server_ip: {server_ip} [{server_ip_type}],\nserver_port: {server_port} [{server_port_type}]"\
            .format(
                server_ip=self.server_ip,
                server_ip_type=type(self.server_ip),
                server_port=self.server_port,
                server_port_type=type(self.server_port),
                ))

        self.conn = None
        for i in range(10):
            try:
                self.conn = socket.create_connection((self.server_ip, self.server_port), timeout=20)
                break
            except EnvironmentError, err:
                if err.errno == 61:
                    print(">>>> Connection refused.")
                    time.sleep(1)

                else:
                    print("EXCEPTION: errno: {errno}".format(errno=err.errno))
                    print_exc()
                    sys.exit(-1)

        if self.conn:
            state = EmissionThread_state_INIT
             
            #while True:
            for i in range(10):
                if state == EmissionThread_state_INIT:
                    self.pull_full_param("lol")
        else:
            print("WE FAILED") 
