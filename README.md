Backup and restore Zimbra Open Source online

# Installation/Upgrade

Requires pip or installation of specific distro packages python-argparse and python-ldap

```
curl --silent -L https://raw.githubusercontent.com/sandromello/zbackup/master/bootstrap.sh | sudo sh -s --
```

Configure and admin account with privileges of admin, you can create one with the following command

```
su - zimbra
zmprov ca zbackup@mydomain.tld VERYSTRONGPASSWORD zimbraIsAdminAccount TRUE
```

Then configure the directives admin_user and admin_password into /opt/zimbra/conf/zbackup.ini and it's done!

#### Configuration

/opt/zimbra/conf/zbackup.ini

#### Logs

/opt/zimbra/log/zbackup.log

### Backup commands

All commands must be executed as zimbra user

```
# Start a full backup. The process goes to background
zbackup -f all

# Start a full backup and hold the tty until it finishes
zbackup -f all --sync

# Start a full backup backup and hold the tty and output the log execution into stdout
zbackup -f all --sync --debug

# Start a full backup from a specific time (10 June of 2015 at 00h00:00 untill now)
zbackup -f all --fromtime 20150610000000

# Start a full backup from documents and contacts
zbackup -f all --ctypes document,contact

# Start a full backup from ldap only
zbackup --ldap

# Start a full backup from specific accounts
zbackup -f bunny@lab.com,roco@lab.com

# Abort a backup process
zbackup --abort full-20150704.184115.839733
```
### Query Backups

```
# Query for all backups
zbackupquery

# Query for a specific label
zbackupquery --label full-20150704.184115.839733
```

### Restoring accounts

```
# Restore a backup from the same account and debug output to stdout
zrestore --label full-20150704.174105.704455 -a admin@lab.com --sync --debug

# Restore a backup to a different account.
zrestore --label full-20150704.174105.704455 -a admin@lab.com --to admin2@lab.com

# Restore account by content types contacts and documents
zrestore --label full-20150704.174105.704455 -a admin@lab.com --ctypes contact,document

# Restore account and put its content to a specific folder. If does not exist the restore will fail
zrestore --label full-20150704.174105.704455 -a admin@lab.com --ctypes message --destfolder /Backup

# Retore account and do not prompt for warnings
zrestore --label full-20150704.174105.704455 -a admin@lab.com -f

# Retore account and reset the content before restoring it
zrestore --label full-20150704.174105.704455 -a admin@lab.com --resolve reset
```