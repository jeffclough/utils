#!/usr/bin/env python3

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# This script needs to operate across a wide range of Python versions as far
# back as 2.4 (yikes!), which means that its exception handling syntax needs to
# avoid either of these forms:
#
#     # The old way.
#     except Exception,e:
# or
#     # The new way.
#     except Exception as e:
#
# The solution I've chosen (shamelessly ripping it of from a web search) is:
#
#     # The version-indifferent way.
#     except Exception:
#       _,e,_=sys.exc_info()
#
# This is a Python-version-indifferent form of exception handling that lets me
# run on even ancient versions where I need to.
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

import gzip,optparse,os,re,shutil,stat,sys,time

# By defalt, files with any of these extensions keep their extension when
# they are renamed with a timestamp.
extensions='''
  .3ctype .3fr .a .ac .aiff .ani .anim .ar .arc .ari .arw .asc .asm .awk .bay
  .bin .bmp .bom .book .bsd .c .c++ .cache .cc .cdf .cfg .cgm .cix .class .cmd
  .coffee .collection .com .conf .config .cpp .cr2 .crl .crw .css .csv .cvf .d
  .data .db .dcr .dcs .dev .djvu .dll .dng .doc .docx .drf .dtml .dylib .egg
  .eip .el .eot .eps .epub .erf .exe .exif .fff .gif .git .gnu .gpg .gz .h .hdr
  .help .hpp .htm .html .hts .ico .iiq .inc .info .ini .jar .java .jfif .jpeg
  .jpg .jps .js .jshint .jsm .json .k25 .kdc .key .keystore .kml .l .ldb .lij
  .lnk .lock .log .lrtemplate .lua .m4 .m4a .machelp .makefile .map .markdown
  .mbox .mcl .md .mdc .mef .model .mos .mov .mp3 .mp4 .mpo .mrw .mustache .nef
  .net .new .nib .node .nrw .o .oab .obm .odg .opml .opts .orf .org .otf .pack
  .pak .pal .pbm .pcf .pdf .pef .pem .pgm .php .pict .pimx .pkg .pl .plist .pm
  .png .pnm .pns .postscript .ppm .prefs .prod .psd .psp .psv .psw .ptx .pub
  .pxn .py .pyc .pyd .qyp .r3d .raf .raw .rb .ref .rif .rpm .rtv .rw2 .rwl .rwz
  .scpt .scss .settings .sh .sig .so .sql .sqlite .sqlite3 .sqlitedb .sr2 .srf
  .srw .sst .sublime-keymap .sublime-menu .svg .svn .swf .tab .tar .tcl .test
  .tgz .tif .tiff .todo .tsv .ttf .txt .url .uue .vdi .war .watchr .webm .webp
  .x3f .xaml .xbm .xls .xml .xsd .yaml .z .zip'''.split()

prog=os.path.basename(sys.argv[0])

if hasattr(os.path,'lexists'):
  lexists=os.path.lexists
else:
  # Shamelessly rip off the standard python implementation of os.path.lexists.
  def lexists(path):
    """Test whether a path exists. Returns True for broken links."""

    try:
        st = os.lstat(path)
    except os.error:
        return False
    return True

time_unit_divisors=dict(
  seconds=1,
  minutes=60,
  hours=3600,
  days=86400,
  weeks=604800
)

def time_unit_divisor(unit):
  u=[u for u in time_unit_divisors if u.startswith(unit)]
  if u:
    u=u[0]
  else:
    return None
  return time_unit_divisors[u]

op=optparse.OptionParser(
  usage='Usage: %prog [OPTIONS] filename ...',
  description='''This command renames or coppies, and optionally compresses,
the given file(s) to include the date and time of each respective file. This is
very handy for rotating log files or saving a copy of a script before modifying
it. File permissions and times are preserved, even when copying and/or
compressing.'''
)
op.add_option('--age',metavar='UNITS',dest='age',action='store',default=None,help="Report the age of the file in the given UNITS. No copying or renaming is performed. If no filename is given on the command line, simply output the current (or offset) time in the given UNITS to standard output. UNITS is one of 'seconds', 'minutes', 'hours', 'days', or 'weeks' (or s, m, h, d, or w, or anywhere in between).")
op.add_option('-c','--copy',dest='copy',action='store_true',default=False,help="Copy the file rather than rename it.")
op.add_option('--filename',dest='filename_only',action='store_true',default=False,help="Only output the timestamped filename of the given file(s). No file is actually renamed or copied. The current time is used for any file that does not exist.")
op.add_option('--format',dest='format',action='store',default='%(filename)s.%(time)s',help="Specify a new format for a time-stamped filename. (default: %default)")
op.add_option('-n','--dry-run',dest='dry_run',action='store_true',default=False,help="Don't actually rename any files. Only output the new name of each file as it would be renamed.")
op.add_option('--offset',dest='offset',action='store',default=None,help="Formatted as '[+|-]H:M' or '[+|-]S', where H is hours, M is minutes, and S is seconds, apply the given offset to the time.")
op.add_option('-q','--quiet',dest='quiet',action='store_true',default=False,help="Perform all renaming or copying silently. This option does not silence the --age or the --filename options.")
op.add_option('-t','--time',dest='time',choices=('created','accessed','modified'),default='modified',help="Choose which time to use for the timestamp. The choices are 'created', 'accessed', or 'modified'. (default: %default)")
op.add_option('--time-format',dest='time_format',action='store',default='%Y%m%d_%H%M%S',help="Specify the format for expressing a file's timestamp. (default: %default)")
op.add_option('--utc',dest='utc',action='store_true',default=False,help="Express all times as UTC (no time zone at all).")
op.add_option('-z',dest='zip',action='store_true',default=False,help="The file is compressed with gzip after renaming or copying.")
opt,args=op.parse_args()
if opt.age:
  div=time_unit_divisor(opt.age)
  if div==None:
    print('%s: Bad --age argument: %s'%(prog,opt.age), file=sys.stderr)
    sys.exit(1)
  opt.age=div
if opt.offset:
  # Convert our --offset argument to positive or negative seconds.
  m=re.match(r'(?P<sign>[-+])?((?P<hours>\d+):(?P<minutes>\d+)|(?P<seconds>\d+))$',opt.offset)
  if not m:
    print('%s: Bad --offset argument: %r'%(prog,opt.offset), file=sys.stderr)
    sys.exit(1)
  d=m.groupdict('0')
  for k in d:
    if k=='sign':
      d[k]=(1,-1)[d[k]=='-']
    else:
      d[k]=int(d[k])
  opt.offset=d['sign']*(d['hours']*3600+d['minutes']*60+d['seconds'])
else:
  opt.offset=0

if opt.utc:
  # Compute how far, in seconds, local time is from UTC.
  t=time.mktime(time.localtime()) # Make sure we're all rounding floats the same way.
  utc_offset=int(time.mktime(time.gmtime(t))-t)
else:
  utc_offset=0

if args:
  # This is the usual mode of renaming files according to their time.
  try:
    for f in args:
      # Get the time this file was created, accessed, or modified.
      try:
        if opt.time=='created':
          t=os.stat(f).st_ctime
        elif opt.time=='accessed':
          t=os.stat(f).st_atime
        else:
          t=os.stat(f).st_mtime
      except (IOError,OSError):
        _,e,_=sys.exc_info()
        if e.errno==2 and opt.filename_only:
          # Use the current time if we're in "--filename" mode and there's no such flie.
          t=int(time.time())
        else:
          raise
      # Apply any offset
      t+=utc_offset
      t+=opt.offset
      if opt.age:
        print(int(time.time()-t+utc_offset)/opt.age)
        continue
      # Format the time as a string.
      t=time.strftime(opt.time_format,time.localtime(t))
      # Create the new filename.
      for ext in extensions:
        if f.endswith(ext):
          # Remove the file extension, but remember what we removed.
          f=f[:-len(ext)]
          break
      else:
        # No special file extension found, so remember that.
        ext=None
      filename=opt.format%dict(filename=f,time=t)
      if ext!=None:
        # Re-attach the file extension to our original and new filenames.
        f+=ext
        filename+=ext
      if opt.zip:
        filename+='.gz'
      if opt.filename_only:
        print(filename)
      elif opt.dry_run:
        # Just output the new name of the file.
        if not opt.quiet:
          print("'%s' %s> '%s'"%(f,'-='[opt.copy],filename))
      else:
        # Ensure that there's no existing file by the new filename.
        if lexists(filename):
          sys.stdout.flush()
          sys.stderr.write('%s: file exists: %s\n'%(prog,filename))
          sys.stderr.flush()
          continue
        else:
          if opt.copy or opt.zip:
            # Copy f to filename.
            if not opt.quiet:
              print("'%s' %s> '%s'"%(f,'-='[opt.copy],filename))
            try:
              src=open(f,'rb')
              if opt.zip:
                dst=gzip.GzipFile(filename,'wb')
              else:
                dst=open(filename,'wb')
              shutil.copyfileobj(src,dst)
              dst.close()
              src.close()
              shutil.copystat(f,filename) # Copy file perms and times.
              if not opt.copy:
                os.unlink(f)
            except IOError:
              _,e,_=sys.exc_info()
              sys.stdout.flush()
              sys.stderr.write('%s: %s\n'%(prog,e))
              sys.stderr.flush()
            except:
              raise
          else:
            # Rename f to filename.
            if not opt.quiet:
              print("'%s' -> '%s'"%(f,filename))
            os.rename(f,filename)
  except (IOError,OSError):
    _,e,_=sys.exc_info()
    if e.filename==None:
      print('%s: %s'%(prog,e.strerror), file=sys.stderr)
    else:
      print('%s: %s: %s'%(prog,e.strerror,e.filename), file=sys.stderr)
    sys.exit(2)
else:
  # We're just outputting the current (or offset) time.
  if opt.age:
    print((int(time.time())+opt.offset+utc_offset)/opt.age)
  else:
    print(time.strftime(opt.time_format,time.localtime(time.time()+opt.offset+utc_offset)))
