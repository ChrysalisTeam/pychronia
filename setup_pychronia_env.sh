

SCRIPTDIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

source $SCRIPTDIR/../ENV/bin/activate

export PYTHONPATH="$SCRIPTDIR:$SCRIPTDIR/vendor"  # only needed if the project is not installed in ENV (via "uv sync")

if [ -z "$DJANGO_SETTINGS_MODULE" ]
then
    export DJANGO_SETTINGS_MODULE=pychronia_settings
fi