#!/bin/sh

# print commands, and exit immediately if anything fails
set -e 
set -x

# This shell script is for running an upgrade test in travis-ci/tox
# It does some hacky things to work so we encapsulate them here. 
# specifically, the git repo checked out for the tests is shared between tests
# at least partially, so if you check out different branches then it affects
# other tests and can cause them to fail or be inaccurate.  
# To avoid that, we duplicate the entire git clone into a subdirectory
# and utilize that to do the upgrade test, leaving the original
# git clone unchanged and intact.  

# $1 should be the directory name to copy the repo to. 
# $2 should be the tag we want to start the upgrade from. 
if [[ -z "$1"  ||  -z "$2" ]]; then
    echo "Usage: $0 <dirname> <git_tag>"
    echo "       dirname:  A temp dir name to use, e.g. 'tmpdir'"
    echo "       git_tag:  Git tag to checkout and start the upgrade from"
    exit 1
fi

if [[ "$2" =~ [^a-zA-Z0-9_\.-] ]]; then
  echo "Invalid tag name characters: $2"
  exit 2
fi

if [[ "$1" =~ [^a-zA-Z0-9_\.-] ]]; then
  echo "Invalid directory name characters: $2"
  exit 3
fi

# add a timestamp to the temp dir
# to avoid issues even between PR/push runs of the same test
TMPDIR=$1_$(date +%s%N)

echo "Will copy git repo to $TMPDIR"
echo "Will check out tag $2"

# ensure we have tags to checkout
git fetch --tags
# create copy of our git clone in a temp dir
mkdir -p $TMPDIR
cp -r `ls -A | grep -v "$TMPDIR"` $TMPDIR/
sudo cp -rp .git $TMPDIR/
cd $TMPDIR
# save current hash so we can come back to it
git reset --hard HEAD
git rev-parse HEAD > commit.hash
cat commit.hash
# first install our starting version and clean up
git checkout $2
rm -f django_celery_beat/migrations/*
git checkout django_celery_beat/migrations
# run the migration for the older version
python manage.py migrate django_celery_beat
# now return to previous hash and clean up again
cat commit.hash | git checkout -
# now make sure migrations still work backward and forward
python manage.py migrate django_celery_beat
python manage.py migrate django_celery_beat 0001
python manage.py migrate django_celery_beat
rm -rf $TMPDIR
