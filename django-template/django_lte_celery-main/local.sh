#!/bin/bash

# pass arguments to docker compose afer -f
docker-compose -f docker-compose.local.yml "$@"