:loop

python -m scss scss/metalradiance.scss -o metalradiance.css -I scss -I ../bootstrap-sass/assets/stylesheets -I ../bootstrap-sass/assets/stylesheets/bootstrap -C

rem python -m scss -r -C -I scss -w .\scss -o . --debug-info

TIMEOUT /T 5
goto loop