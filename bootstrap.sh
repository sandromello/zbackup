#!/bin/sh
if ! $(python -c "import ldap" &> /dev/null); then
  command -v pip >/dev/null 2>&1 || { echo >&2 "Requires pip. Aborting..."; exit 1; }
  pip install ldap
fi

if ! $(python -c "import argparse" &> /dev/null); then
  command -v pip >/dev/null 2>&1 || { echo >&2 "Requires pip. Aborting..."; exit 1; }
  pip install argparse
fi

command -v curl >/dev/null 2>&1 || { echo >&2 "Requires wget. Aborting..."; exit 1; }

mkdir /opt/zimbra/zbackup 2> /dev/null
curl -L https://raw.githubusercontent.com/sandromello/zbackup/master/conf/zbackup.ini -o /opt/zimbra/conf/zbackup.ini
curl -L https://raw.githubusercontent.com/sandromello/zbackup/master/zbackup/__init__.py -o /opt/zimbra/zbackup/__init__.py
curl -L https://raw.githubusercontent.com/sandromello/zbackup/master/zbackup/common.py -o /opt/zimbra/zbackup/common.py

curl -L https://raw.githubusercontent.com/sandromello/zbackup/master/bin/zbackup -o /opt/zimbra/bin/zbackup
curl -L https://raw.githubusercontent.com/sandromello/zbackup/master/bin/zrestore -o /opt/zimbra/bin/zrestore
curl -L https://raw.githubusercontent.com/sandromello/zbackup/master/bin/zbackupquery -o /opt/zimbra/bin/zbackupquery

chown 600 /opt/zimbra/conf/zbackup.ini
chown 755 /opt/zimbra/bin/zbackupquery
chown 755 /opt/zimbra/bin/zbackup
chown 755 /opt/zimbra/bin/zrestore