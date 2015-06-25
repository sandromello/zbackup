#!/bin/sh
if ! $(python -c "import ldap" &> /dev/null); then
  command -v pip >/dev/null 2>&1 || { echo >&2 "Requires pip. Aborting..."; exit 1; }
  pip install ldap
fi

if ! $(python -c "import argparse" &> /dev/null); then
  command -v pip >/dev/null 2>&1 || { echo >&2 "Requires pip. Aborting..."; exit 1; }
  pip install argparse
fi

command -v curl >/dev/null 2>&1 || { echo >&2 "Requires curl. Aborting..."; exit 1; }

if [ ! -d "/opt/zimbra" ]; then
  echo "Zimbra is not installed. Aborting..."; exit 1
fi

mkdir /opt/zimbra/zbackup 2> /dev/null
curl --silent -L https://raw.githubusercontent.com/sandromello/zbackup/master/conf/zbackup.ini -o /opt/zimbra/conf/zbackup.ini
curl --silent -L https://raw.githubusercontent.com/sandromello/zbackup/master/zbackup/__init__.py -o /opt/zimbra/zbackup/__init__.py
curl --silent -L https://raw.githubusercontent.com/sandromello/zbackup/master/zbackup/common.py -o /opt/zimbra/zbackup/common.py

curl --silent -L https://raw.githubusercontent.com/sandromello/zbackup/master/bin/zbackup -o /opt/zimbra/bin/zbackup
curl --silent -L https://raw.githubusercontent.com/sandromello/zbackup/master/bin/zrestore -o /opt/zimbra/bin/zrestore
curl --silent -L https://raw.githubusercontent.com/sandromello/zbackup/master/bin/zbackupquery -o /opt/zimbra/bin/zbackupquery

chown zimbra. /opt/zimbra/conf/zbackup.ini
chmod 600 /opt/zimbra/conf/zbackup.ini

chmod 755 /opt/zimbra/bin/zbackupquery
chmod 755 /opt/zimbra/bin/zbackup
chmod 755 /opt/zimbra/bin/zrestore
echo "Installation completed!"