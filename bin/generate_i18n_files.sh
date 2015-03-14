

SCRIPT=$(readlink -f $0)
SCRIPTDIR=`dirname $SCRIPT`
ROOTDIR=`dirname $SCRIPTDIR`
cd $ROOTDIR


if [ -n "$DJANGO_SETTINGS_MODULE" ]
then
    echo "Using root manage.py with django settings '$DJANGO_SETTINGS_MODULE'"
    manager="../manage.py"
else
    echo "Using 'tests/' manage.py launchers with their own django settings"
    manager="tests/manage.py"
fi

for mydir in pychronia_game pychronia_cms pychronia_common
do
    pushd $mydir
    python $manager makemessages -l fr
    # HERE - manually use virtaal to translate messages efficiently
    python $manager compilemessages
    popd
done







