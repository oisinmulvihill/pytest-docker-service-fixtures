Pytest Docker backed Service Fixtures
=====================================

Introduction
-------------

This provides a series of fixtures which can be used in pytests to aid to
integration and other forms of testing. This project used the lower level
docker control logic from my other library https://github.com/oisinmulvihill/docker-testingaids
I'll flesh this out more as I share work I have between two private ventures.


Env Set Up
----------

You need to create the dk_config.yaml file in your home directory. This
configures the mapping of service to docker container used. It also specifies
which port to wait for when readiness testing. The ports section lists the
ports to be exposed from the containers. This will be mapped to random local
ports. This allows concurrent tests runs without interference. You can query
for the port chosen at random for the service. Once the file is created export
the DK_CONFIG variable to point to absolute path to the dk_config.yaml


This is a list of my general containers. I usually also have internal private
containers list here too.

.. sourcecode:: yaml

    docker:
        base_url: unix://var/run/docker.sock

    containers:
        influxdb:
            image: tutum/influxdb
            interface: 0.0.0.0
            entrypoint:
            auth:
                user: root
                password: root
            export:
                wait_for_port: db
                ports:
                    - port: 8083
                      name: admin
                    - port: 8086
                      name: db

        rethinkdb:
            image: dockerfile/rethinkdb:latest
            interface: 0.0.0.0
            auth:
                user:
                password:
            entrypoint:
            export:
                wait_for_port: db
                ports:
                    - port: 8080
                      name: admin
                    - port: 28015
                      name: db

        redis:
            image: redis
            interface: 0.0.0.0
            auth:
                user:
                password:
            entrypoint:
            export:
                db: 2
                wait_for_port: db
                ports:
                    - port: 6379
                      name: db

        elasticsearch:
            image: dockerfile/elasticsearch
            interface: 0.0.0.0
            auth:
                user:
                password:
            entrypoint:
            export:
                wait_for_port: db
                ports:
                    - port: 9200
                      name: db
