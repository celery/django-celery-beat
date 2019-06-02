#! /usr/bin/env bash
# Copyright (C) 2019 Sebastian Pipping <sebastian@pipping.org>
# Licensed under the BSD License (3 clause, also known as the new BSD license)

set -e

PS4='# '
set -x

wait-for-it django:8000  # due to migrations

exec "$@"
