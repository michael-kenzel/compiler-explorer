@echo off

REM helper script used by setup_msvc_config.py to extract the relevant 
REM bits of information from the environment set up by vcvarsall.bat

echo --{
where cl
echo %INCLUDE%
echo %LIB%
where undname
echo }--
