#!/usr/bin/env python3

import argparse, gzip, os, re, shutil, stat, sys, time

# By defalt, files with any of these extensions keep their extension when
# they are renamed with a timestamp.
# TODO: Make these extensions configurable to the user in some persistent way.
extensions = """
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
  .x3f .xaml .xbm .xls .xml .xsd .yaml .z .zip""".split()

prog = os.path.basename(sys.argv[0])

def warn(msg):
    "Write msg to stderr preceded with the name of this program."

    sys.stderr.flush()
    print(f"{prog}: {msg}",file=sys.stderr)
    sys.stderr.flush()

def die(msg=None,rc=1):
    """Write msg, if any, to stderr preceded with the name of this program, and
    terminate with return code 1 (by default)."""

    if msg:
        print(f"{prog}: {msg}",file=sys.stderr)
    sys.exit(rc)

def parse_args():
    def time_unit_divisor(unit):
        time_unit_divisors = dict(
            seconds=1, minutes=60, hours=3600, days=86400, weeks=604800
        )
        u = [u for u in time_unit_divisors if u.startswith(unit)]
        if u:
            u = u[0]
        else:
            return None
        return time_unit_divisors[u]

    ap = argparse.ArgumentParser(
        description="""This command renames or copies, and optionally
        compresses, the given file(s) to include the date and time of each
        respective file. This is very handy for rotating log files or saving a
        copy of a script before modifying it. File permissions and times are
        preserved, even when copying and/or compressing."""
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Output debugging information.",
    )
    ap.add_argument(
        "--age",
        metavar="UNITS",
        dest="age",
        action="store",
        default=None,
        help="Report the age of the file in the given UNITS. No copying or renaming is performed. If no filename is given on the command line, simply output the current (or offset) time in the given UNITS to standard output. UNITS is one of 'seconds', 'minutes', 'hours', 'days', or 'weeks' (or s, m, h, d, or w, or anywhere in between).",
    )
    ap.add_argument(
        "-c",
        "--copy",
        dest="copy",
        action="store_true",
        default=False,
        help="Copy the file rather than rename it.",
    )
    ap.add_argument(
        "--filename",
        dest="filename_only",
        action="store_true",
        default=False,
        help="Only output the timestamped filename of the given file(s). No file is actually renamed or copied. The current time is used for any file that does not exist.",
    )
    ap.add_argument(
        "--format",
        dest="format",
        action="store",
        default="%(filename)s.%(time)s",
        help="Specify a new format for a time-stamped filename. (default: %(default)s)",
    )
    ap.add_argument(
        "-n",
        "--dryrun",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Don't actually rename any files. Only output the new name of each file as it would be renamed.",
    )
    ap.add_argument(
        "--offset",
        dest="offset",
        action="store",
        default=None,
        help="Formatted as '[+|-]H:M' or '[+|-]S', where H is hours, M is minutes, and S is seconds, apply the given offset to the time.",
    )
    ap.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        default=False,
        help="Perform all renaming or copying silently. This option does not silence the --age or the --filename options.",
    )
    ap.add_argument(
        "-t",
        "--time",
        dest="time",
        choices=("created", "accessed", "modified"),
        default="modified",
        help="Choose which time to use for the timestamp. The choices are 'created', 'accessed', or 'modified'. (default: %(default)s)",
    )
    ap.add_argument(
        "--time-format",
        dest="time_format",
        action="store",
        default="%Y%m%d_%H%M%S",
        help="Specify the format for expressing a file's timestamp. (default: %(default)s)",
    )
    ap.add_argument(
        "--utc",
        dest="utc",
        action="store_true",
        default=False,
        help="Express all times as UTC (no time zone at all).",
    )
    ap.add_argument(
        "-z",
        dest="zip",
        action="store_true",
        default=False,
        help="The file is compressed with gzip after renaming or copying.",
    )
    ap.add_argument(
        'args',
        metavar='FILENAME',
        nargs='*',
        help="List of files to be timestamped.",
    )
    opt = ap.parse_args()

    if opt.age:
        div = time_unit_divisor(opt.age)
        if div == None:
            die(f"Bad --age value: {opt.age!r}")
        opt.age = div
    if opt.offset:
        # Convert our --offset argument to positive or negative seconds.
        m = re.match(
            r"(?P<sign>[-+])?((?P<hours>\d+):(?P<minutes>\d+)|(?P<seconds>\d+))$",
            opt.offset,
        )
        if not m:
            die(f"Bad --offset value {opt.offset!r}")
        d = m.groupdict("0")
        for k in d:
            if k == "sign":
                d[k] = (1, -1)[d[k] == "-"]
            else:
                d[k] = int(d[k])
        opt.offset = d["sign"] * (d["hours"] * 3600 + d["minutes"] * 60 + d["seconds"])
    else:
        opt.offset = 0

    if opt.utc:
        # Compute how far, in seconds, local time is from UTC.
        t = time.mktime(
            time.localtime()
        )  # Make sure we're all rounding floats the same way.
        opt.utc_offset = int(time.mktime(time.gmtime(t)) - t)
    else:
        opt.utc_offset = 0

    return opt

def main():
    opt=parse_args()
    if opt.args:
        # This is the usual mode of renaming files according to their time.
        try:
            for f in opt.args:
                # Get the time this file was created, accessed, or modified.
                try:
                    if opt.time == "created":
                        t = os.stat(f).st_ctime
                    elif opt.time == "accessed":
                        t = os.stat(f).st_atime
                    else:
                        t = os.stat(f).st_mtime
                except (IOError, OSError) as e:
                    if e.errno == 2 and opt.filename_only:
                        # Use the current time if we're in "--filename" mode
                        # and there's no such flie.
                        t = int(time.time())
                    else:
                        raise
                # Apply any offset
                t += opt.utc_offset
                t += opt.offset
                if opt.age:
                    print(int(time.time() - t + opt.utc_offset) / opt.age)
                    continue
                # Format the time as a string.
                t = time.strftime(opt.time_format, time.localtime(t))
                # Create the new filename.
                for ext in extensions:
                    if f.endswith(ext):
                        # Remove the file extension, but remember what we removed.
                        f = f[: -len(ext)]
                        break
                else:
                    # No special file extension found, so remember that.
                    ext = None
                filename = opt.format % dict(filename=f, time=t)
                if ext != None:
                    # Re-attach the file extension to our original and new filenames.
                    f += ext
                    filename += ext
                if opt.zip:
                    filename += ".gz"
                if opt.filename_only:
                    print(filename)
                elif opt.dry_run:
                    # Just output the new name of the file.
                    if not opt.quiet:
                        print("'%s' %s> '%s'" % (f, "-="[opt.copy], filename))
                else:
                    # Ensure that there's no existing file by the new filename.
                    if os.path.lexists(filename):
                        warn(f"File already exists: {filename!r}")
                        continue
                    else:
                        if opt.copy or opt.zip:
                            # Copy f to filename.
                            if not opt.quiet:
                                print("'%s' %s> '%s'" % (f, "-="[opt.copy], filename))
                            try:
                                src = open(f, "rb")
                                if opt.zip:
                                    dst = gzip.GzipFile(filename, "wb")
                                else:
                                    dst = open(filename, "wb")
                                shutil.copyfileobj(src, dst)
                                dst.close()
                                src.close()
                                shutil.copystat(f, filename)  # Copy file perms and times.
                                if not opt.copy:
                                    os.unlink(f)
                            except IOError as e:
                                warn(str(e))
                            except:
                                raise
                        else:
                            # Rename f to filename.
                            if not opt.quiet:
                                print("'%s' -> '%s'" % (f, filename))
                            os.rename(f, filename)
        except (IOError, OSError) as e:
            if e.filename:
                die(f"{e.strerror}: {e.filename}")
            else:
                die(e.strerror)
    else:
        # We're just outputting the current (or offset) time.
        if opt.age:
            print((int(time.time()) + opt.offset + opt.utc_offset) / opt.age)
        else:
            print(
                time.strftime(
                    opt.time_format, time.localtime(time.time() + opt.offset + opt.utc_offset)
                )
            )

if __name__=="__main__":
    main()
