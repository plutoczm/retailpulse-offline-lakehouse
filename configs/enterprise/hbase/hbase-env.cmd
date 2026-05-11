@echo off
rem RetailPulse Windows-friendly HBase client options.
rem HBase's packaged Windows env file may enable UseConcMarkSweepGC, which is
rem removed in modern Java. Keep only safe client options for Java 17.

set HBASE_OPTS=%HBASE_OPTS% "-Djava.net.preferIPv4Stack=true"
set HBASE_MANAGES_ZK=false

