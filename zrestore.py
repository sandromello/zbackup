#!/usr/bin/env python
import argparse, sys, os, signal, shelve
from datetime import datetime
from traceback import format_exc

sys.path.insert(0, '/opt/zimbra')
from zbackup.common import ZBackupRequest, CONTENT_TYPES

BACKUP_DESTINATION = os.environ.get('ZIMBRA_HOME')
if not BACKUP_DESTINATION:
  print 'Could not find env variable ZIMBRA_HOME'
  sys.exit(1)

BACKUP_DESTINATION += '/backup'

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Zimbra Restore line command')
  parser.add_argument('--ctypes', metavar='<message,content,appointment,task,document>',
    help='which content to restore: message,contact,appointment,task,document. Default: all')
  parser.add_argument('-a', metavar='<account>', help='Start a restore for a specific account', required=True)
  parser.add_argument('--resolve', metavar='<ignore|modify|replace|reset>', 
    help='Resolve duplicates. ignore. modify: update older items. reset: delete the old subfolder. replace: replace the existing items. Default: ignore')
  parser.add_argument('--destfolder', metavar='<destfolder>', help='Destination folder to restore')
  parser.add_argument('--sync', action='store_true', help='Runs restore synchronously.')
  parser.add_argument('--label', metavar='<label>', help='Specify the label for restoring', required=True)
  parser.add_argument('--debug', action='store_true', help='Turn on debuging')
  parser.add_argument('--target', metavar='</path/to/backup>', help='Backup target location (default <zimbra_home>/backup)')
  
  args = parser.parse_args()

  debug, ctypes = (False, None)
  if args.ctypes:
    if [ctype for ctype in args.ctypes.split(',') if ctype not in CONTENT_TYPES]:
      print 'Content Type error. Accept only: %s' % ','.join(CONTENT_TYPES)
      print parser.print_help()
      sys.exit(1)

  BACKUP_DESTINATION = args.target or BACKUP_DESTINATION
  
  args.resolve = args.resolve or 'ignore'
  args.destfolder = args.destfolder or ''

  if args.debug:
    debug = True

  try:
    zcr = ZBackupRequest(args.a, BACKUP_DESTINATION, debug=debug, ctypes=args.ctypes)
    zcr.run_restore(label=args.label, resolve=args.resolve, dest_folder=args.destfolder, sync=args.sync)
  except Exception, e:
    if args.sync:
      print 'Error running restore: %s' % e
    if args.debug:
      print format_exc()
    sys.exit(1)