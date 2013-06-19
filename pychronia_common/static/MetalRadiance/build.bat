:loop

python -m scss scss/main.scss -o metalradiance.css -I scss -C 

python -m scss scss/main_mobile.scss -o metalradiance_mobile.css -I scss -C 

rem python -m scss -r -C -I scss -w .\scss -o . --debug-info

TIMEOUT /T 5
goto loop