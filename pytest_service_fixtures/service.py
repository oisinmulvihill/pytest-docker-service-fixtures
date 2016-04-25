# -*- coding: utf-8 -*-
"""
Oisin Mulvihill
2015-02-06

"""
import os
import sys
import uuid
import socket
import logging
import tempfile
import StringIO
import subprocess
import ConfigParser
from string import Template

import pytest
from evasion.common import net

# imported so request.getfuncargvalue will find:
from testing.aid.containers import dk_logger
from testing.aid.containers import dk_config
from testing.aid.containers import dk_influxdb
from testing.aid.containers import dk_redis
from testing.aid.containers import dk_redis_session
from testing.aid.containers import dk_rethinkdb
from testing.aid.containers import dk_rethinkdb_session
from testing.aid.containers import dk_elasticsearch


def get_log(e=None):
    return logging.getLogger("{0}.{1}".format(__name__, e) if e else __name__)


@pytest.fixture(scope='function')
def elasticsearch(request):
    """Set up a elasticsearch reset and ready to roll.
    """
    log = get_log('elasticsearch')

    edb = request.getfuncargvalue('dk_elasticsearch')

    class Conn(object):
        def __init__(self):
            """Returned so others can ask for what port, host elasticsearch
            is running on.
            """
            ports = edb.settings['export']['ports']
            port = [p['export_port'] for p in ports if p['name'] == 'db']
            port = port[0]
            self.host = edb.settings['interface']
            self.port = port
            self.base_uri = 'http://{}:{}'.format(self.host, self.port)

    from pnc.user.index import db
    from pnc.user.index import document

    es_db = Conn()
    db.init(dict(es_endpoint=es_db.base_uri))
    log.info('Configuring indices for {}'.format(es_db.base_uri))
    document.init_indices()
    log.info('database ready for testing "{}"'.format(es_db.base_uri))

    def db_teardown(x=None):
        db.conn().hard_reset()
        log.warn(
            'teardown of "{}" OK.'.format(es_db.base_uri)
        )

    request.addfinalizer(db_teardown)

    return es_db


@pytest.fixture(scope='session')
def rethink_db_name_session(request):
    """Return the a unqiue db name to use for a tests running in a session.
    """
    return "testingdb_{}".format(uuid.uuid4().hex)


def _rethinkdb_setup(request):
    log = get_log('_rethinkdb_setup')

    redb = request.getfuncargvalue('dk_rethinkdb_session')
    db_name = request.getfuncargvalue('rethink_db_name_session')

    class Conn(object):
        def __init__(self):
            """Returned so others can ask for what port, host, etc rethinkdb
            is running on.
            """
            ports = redb.settings['export']['ports']
            port = [p['export_port'] for p in ports if p['name'] == 'db']
            port = port[0]
            self.host = redb.settings['interface']
            self.port = port
            self.db_name = db_name

    rdb = Conn()
    log.info("Rethinkdb host={} port={} db={}".format(
        rdb.port, rdb.host, rdb.db_name
    ))

    return rdb


@pytest.fixture(scope='session')
def rethinkdb_persist(request):
    """Set up a rethinkdb ready to roll once per complete test run.
    """
    return _rethinkdb_setup(request)


@pytest.fixture(scope='session')
def redis_session(request):
    """Set up a redis reset and ready to roll.
    """
    log = get_log('redis_session')

    redb = request.getfuncargvalue('dk_redis_session')

    class Conn(object):
        def __init__(self):
            """Returned so others can ask for what port, host, etc redis
            is running on.
            """
            ports = redb.settings['export']['ports']
            port = [p['export_port'] for p in ports if p['name'] == 'db']
            port = port[0]
            # cache db:
            self.db = redb.settings['export'].get('db', 2)
            # RQ worker / task queue
            self.defer_db = redb.settings['export'].get('defer_db', 6)
            self.host = redb.settings['interface']
            self.port = port

        def conn(self):
            import redis
            return redis.StrictRedis(
                host=self.host, port=self.port, db=self.db
            )

    rdb = Conn()
    log.debug(
        "redis config host '{}' port '{}' db '{}'.".format(
            rdb.host, rdb.port, rdb.db
        )
    )

    def db_teardown(x=None):
        # log.warn('Dropping all from redis db: {}'.format(
        #     rdb.conn().defer_db
        # ))
        # rdb.conn().flushall()
        log.warn('teardown OK.')

    request.addfinalizer(db_teardown)

    return rdb


@pytest.fixture(scope='function')
def redis(request):
    """Uses the long running session redis and resets the db after each test.
    """
    log = get_log('redis')

    rdb = request.getfuncargvalue('redis_session')

    def db_teardown(x=None):
        log.warn('Cleaing up redis db')
        rdb.conn().flushall()
        log.warn('teardown OK.')

    request.addfinalizer(db_teardown)

    return rdb


@pytest.fixture(scope='session')
def redis_persist(request):
    """Uses the long running session redis.
    """
    log = get_log('redis')

    rdb = request.getfuncargvalue('redis_session')

    def db_teardown(x=None):
        log.warn('Cleaing up redis db')
        rdb.conn().flushall()
        log.warn('teardown OK.')

    request.addfinalizer(db_teardown)

    return rdb


@pytest.fixture(scope='function')
def influxdb(request):
    """Set up a influxdb connection reset and ready to roll.
    """
    log = get_log('influxdb')

    influxdb = request.getfuncargvalue('dk_influxdb')

    class Conn(object):
        def __init__(self):
            """Returned so others can ask for what port, host, etc influx
            is running on.
            """
            ports = influxdb.settings['export']['ports']
            port = [p['export_port'] for p in ports if p['name'] == 'db']
            port = port[0]
            self.host = influxdb.settings['interface']
            self.port = port
            self.user = influxdb.settings['auth']['user']
            self.password = influxdb.settings['auth']['password']
            self.db = "testingdb_{}".format(uuid.uuid4().hex)
            log.debug("InfluxDB port={} host={} db={}".format(
                self.port, self.host, self.db
            ))

    dbconn = Conn()

    return dbconn


def free_tcp_port():
    """Return a free socket port we can listen to.

    :returns: A TCP Port to listen on.

    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    tcp_port = s.getsockname()[1]
    s.close()

    return tcp_port


class BasePyramidServerRunner(object):
    """Start/Stop the testserver for Pyramid based web testing purposes.
    """
    def __init__(self, config={}, test_config_name='test_cfg.ini'):
        """
        """
        self.log = get_log("ServerRunner")
        self.serverPid = None
        self.serverProcess = None

        self.port = int(config.get('port', free_tcp_port()))
        self.interface = config.get('interface', '127.0.0.1')

        # Add in so when template is rendered this are found:
        if 'host' not in config:
            config['host'] = self.interface

        if 'port' not in config:
            config['port'] = self.port

        self.URI = "http://%s:%s" % (self.interface, self.port)

        # Make directory to put file and other data into:
        self.test_dir = tempfile.mkdtemp()
        self.log.info("Test Server temp directory <%s>" % self.test_dir)

        # Get template and render to the test director:
        cfg_tmpl = Template(self.template_config())
        data = cfg_tmpl.substitute(config)
        self.temp_config = os.path.join(self.test_dir, test_config_name)
        with open(self.temp_config, "wb") as fd:
            fd.write(data)
        self.log.debug("test run directory '{}' test config '{}'".format(
            self.test_dir,
            self.temp_config,
        ))
        self.config = ConfigParser.ConfigParser()
        self.config.readfp(StringIO.StringIO(data))
        config = ConfigParser.ConfigParser(dict(here=self.test_dir))
        config.read(self.temp_config)

        # The service to run with the rendered configuration:
        self.cmd = "pserve {}".format(self.temp_config)

    def template_config(self):
        """Return the python string template INI file contents to use.
        """
        raise NotImplementedError("Implent to return ")

    def cleanup(self):
        """Clean up temp files and directories.
        """
        for f in [self.temp_config]:
            try:
                os.remove(f)
            except OSError:
                os.system('rm {}'.format(f))
        try:
            os.removedirs(self.test_dir)
        except OSError:
            os.system('rm -rf {}'.format(self.test_dir))

    def start(self):
        """Spawn the web app in testserver mode.

        After spawning the web app this method will wait
        for the web app to respond to normal requests.

        """
        self.log.info(
            "start: running <%s> in <%s>." % (self.cmd, self.test_dir)
        )

        # Spawn as a process and then wait until
        # the web server is ready to accept requests.
        #
        self.serverProcess = subprocess.Popen(
            args=self.cmd,
            shell=True,
            cwd=self.test_dir,
        )
        pid = self.serverProcess.pid

        if not self.isRunning():
            raise SystemError("%s did not start!" % self.cmd)

        #self.log.debug("start: waiting for '%s' readiness." % self.URI)
        net.wait_for_ready(self.URI + "/ping", timeout=2)

        return pid

    def stop(self):
        """Stop the server running."""
        self.log.info("stop: STOPPING Server.")

        # Stop:
        if self.isRunning():
            self.serverProcess.terminate()
            os.waitpid(self.serverProcess.pid, 0)

        # Make sure its actually stopped:
        if sys.platform.startswith('win'):
            subprocess.call(
                args="taskkill /F /T /IM pserve.exe",
                shell=True,
            )
        else:
            subprocess.call(
                args=(
                    'ps -a | grep -v grep | grep "pserve*" '
                    '| awk \'{print "kill -15 "$1}\' | sh'
                ),
                shell=True,
            )

    def isRunning(self):
        """Called to testserver

        returned:
            True - its running.
            False - its not running.

        """
        returned = False
        process = self.serverProcess

        if process and process.poll() is None:
            returned = True

        return returned
