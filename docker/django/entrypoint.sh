#! /usr/bin/env bash
# Copyright (C) 2019 Sebastian Pipping <sebastian@pipping.org>
# Licensed under the BSD License (3 clause, also known as the new BSD license)

set -e

PS4='# '
set -x

wait-for-it postgres:5432

python3 manage.py migrate

python3 manage.py createsuperuserwithpassword \
        --username admin \
        --password admin \
        --email admin@example.org \
        --preserve

exec "$@"
