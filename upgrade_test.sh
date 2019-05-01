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

echo "Will copy git repo to $1"
echo "Will check out tag $2"

# must use older versions for starting with older celery-beat
pip install "django>=1.11.17,<2.0"
pip install "celery<5.0.0"
pip list
git fetch --tags
# create copy of our git clone in a temp dir
rm -rf $1
mkdir -p $1
cp -r `ls -A | grep -v "$1"` $1/
sudo cp -rp .git $1/
cd $1
# save current hash so we can come back to it
git reset --hard HEAD
git rev-parse HEAD > commit.hash
cat commit.hash
# first install our starting version and clean up
git checkout $2
# run the migration for the older version
python manage.py migrate django_celery_beat
# now return to previous hash and clean up again
cat commit.hash | git checkout -
# now make sure migrations still work backward and forward
python manage.py migrate django_celery_beat
python manage.py migrate django_celery_beat 0001
python manage.py migrate django_celery_beat
