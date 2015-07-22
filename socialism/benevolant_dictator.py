#!/usr/bin/env python2
from __future__ import print_function, with_statement, division, generators

""" Extremely simple launch script. Should be improved. """
import os, sys, re, threading, socket, time
import subprocess as sp
import param_serv.server


from param_serv.param_utils import *
from dbi_utils import search_file
from subprocess import *
from traceback import format_exc

class Server(object):
    def __init__(self):
        pass

    def _launch_server(self):
        db = {}
        db_rlock = threading.RLock()
        meta = {}
        meta_rlock = threading.RLock()

        acceptor = param_serv.server.AcceptorThread(
            meta=meta,
            meta_rlock=meta_rlock,
            db=db,
            db_rlock=db_rlock,
            )

        self.port = acceptor.bind()
        acceptor.start()
        return acceptor

    def _launch_multiple(
        self,
        script_path,
        project_name,
        walltime,
        number_of_nodes,
        number_of_gpus,
        job_name,
        task_name,
        procs_per_job,
        lower_bound,
        upper_bound,
        user_args="",
        debug=False,
        debug_pycharm=False,
        is_qsub=False,
        is_jobdispatch=True,
    ):

########################################################
# grunt work
########################################################
        pydev = ""
        executable = "python2"

        ############
        # function argument/param consistency check; this is a directly user exposed function.
        # TODO: this, tightly, when we have consistent basic functionality
        ############
        assert procs_per_job >= 1, "There needs to be at least one process per job."

        ############
        # Create the shell script that is going to be used to launch the jobs.
        # TODO: add jobdispatch integration
        ############

        to_export = {}

        to_export["SOCIALISM_project_name"] =     project_name
        to_export["SOCIALISM_walltime"] =         str(walltime)
        to_export["SOCIALISM_number_of_nodes"] =  str(number_of_nodes)
        to_export["SOCIALISM_number_of_gpus"] =   str(number_of_gpus)
        to_export["SOCIALISM_job_name"] =         job_name
        to_export["SOCIALISM_task_name"] =        task_name
        to_export["SOCIALISM_procs_per_job"] =    str(procs_per_job)
        to_export["SOCIALISM_script_path"] =      script_path
        to_export["SOCIALISM_server_ip"] =        our_ip()
        to_export["SOCIALISM_server_port"] =      str(self.port)
        to_export["SOCIALISM_debug"] =            str(debug).lower()


########################################################
# pycharm remote debugging
########################################################
        if debug_pycharm:
            # find the debugging process
            sys.path.append("/Applications/PyCharm CE.app/Contents/helpers/pydev/")
            import pydevd
            import re
            debug_procs = os.popen("ps -A | grep pydevd | grep -v grep").read().split("\n")
            debugger_is_running = debug_procs[0] != ''

            if debugger_is_running:
                # extract the port of the debug server
                print("< app found a debugger >")
                res = debug_procs[0] # there could be more than one. eventually, we could use this if we need to
                port = re.findall("--port \w+", res)[0].split()[1]
                print("trying port {port}".format(port=port))
                pydev = '/Applications/PyCharm CE.app/Contents/helpers/pydev/'

                # change the executable
                executable = "python2 -m pydevd --multiproc --client 127.0.0.1 --port {port} --file ".format(port=port)
        launch_template = \
            """
            #PBS -A {project_name}
            #PBS -l walltime={walltime}
            #PBS -l nodes={number_of_nodes}:gpus={number_of_gpus}
            #PBS -r n
            #PBS -N {job_name}

            export PYTHONPATH="$PYTHONPATH":"{pydev}"

            for i in $(seq 0 $(expr {procs_per_job} - 1))
            do
                echo "starting job $i"
                {executable} '{script_path}' '{user_args}' &
            done
            wait
            echo "qsub like script done"
            """ \
            .format(
            executable=       executable,
            user_args=        user_args,
            project_name=     project_name,
            walltime=         walltime,
            number_of_nodes=  number_of_nodes,
            number_of_gpus=   number_of_gpus,
            job_name=         job_name,
            pydev=            pydev,
            procs_per_job=    procs_per_job,
            script_path=      script_path,
            )


        if debug:
            env = {
                "PBS_NODENUM": "0",
                }

            # add some fake qsub env variables to emulate those that would be present at the time of execution
            env_code = "\n".join(["export {key}={value};".format(key=key, value=value) for key, value in env.items()]) + "\n"
            complete_code = env_code + "sh" + launch_template

            # run the script
            process = sp.Popen("sh --debug", shell=True, stdin=sp.PIPE, stdout=sys.stdout)
            stdout = process.communicate(complete_code)[0]

        if is_qsub:

            PATH=os.getenv('PATH')
            dbi_param = {}
            dbi_param['launch_cmd'] = None

            options = ""
            process = sp.Popen("qsub {options}".format(options=options), shell=True, stdin=sp.PIPE, stdout=sys.stdout)
            stdout = process.communicate(launch_template)[0]
        if is_jobdispatch:

            line = ";\n".join([ "export {key}=\'{value}\'".format(key=key, value=value) for key, value in to_export.iteritems()]) + ";\npython2 \'/home/julesgm/task/user_script.py\';"

            template = "jobdispatch --gpu --duree={walltime} \'{line}\'"\
                .format(path=script_path,  walltime=walltime, line=line)

            proc = sp.Popen(template, shell=True, stdin=sp.PIPE, stdout=sys.stdout)

        print("benevolent_dictator - done")