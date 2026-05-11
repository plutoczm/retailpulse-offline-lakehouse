@echo off
rem Sqoop 1.4.7 expects an older commons-cli API than Hadoop 3.x ships.
rem Keep the compatibility jar before Hadoop's commons-cli on Sqoop client commands.
if not defined SQOOP_HOME (
  set SQOOP_HOME=%~dp0..
)

set HADOOP_USER_CLASSPATH_FIRST=true
if exist "%SQOOP_HOME%\lib\commons-cli-1.2.jar" (
  set SQOOP_USER_CLASSPATH=%SQOOP_HOME%\lib\commons-cli-1.2.jar;%SQOOP_USER_CLASSPATH%
)
