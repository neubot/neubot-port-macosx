#!/usr/bin/env python

#
# Copyright (c) 2011-2012
#     Nexa Center for Internet & Society, Politecnico di Torino (DAUIN)
#     and Simone Basso <bassosimone@gmail.com>
#
# This file is part of Neubot <http://www.neubot.org/>.
#
# Neubot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Neubot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Neubot.  If not, see <http://www.gnu.org/licenses/>.
#

''' Make MacOS Neubot packages '''

import traceback
import tarfile
import compileall
import shutil
import os.path
import subprocess
import hashlib
import shlex
import sys

TOPDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#
# This simplifies things a lot.
#
MACOSDIR = os.sep.join([TOPDIR, 'MacOS'])
os.chdir(MACOSDIR)

VERSION = sys.argv[1]
NUMERIC_VERSION = sys.argv[2]

IGNORER = shutil.ignore_patterns('.DS_Store')

def _call(cmdline):
    ''' exit() if the subprocess fails '''
    retval = subprocess.call(shlex.split(cmdline))
    if retval != 0:
        sys.exit(1)

def _sign(sig, tarball):
    """ Make digital signature """
    try:
        filenam = os.sep.join([os.environ['HOME'], '.neubot-macos'])
        filep = open(filenam, 'r')
        privkey = filep.read().strip()
        filep.close()
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        privkey = None
    if not privkey:
        privkey = raw_input('Enter privkey location: ')
    if privkey:
        _call('openssl dgst -sha256 -sign %s -out %s %s' %
           (privkey, sig, tarball))

def _fixup_perms():

    '''
     Fix group ownership: we want wheel and not staff.  This happens
     on MacOS because 'BSD derived systems always have the setgid
     directory behavior.'

     See <http://comments.gmane.org/gmane.os.openbsd.misc/187993>
    '''

    _call(r'find neubot/ -exec chown root:wheel {} \;')
    _call(r'find neubot/ -type d -perm 700 -exec chmod 755 {} \;')
    _call(r'find neubot/ -type f -perm 700 -exec chmod 755 {} \;')
    _call(r'find neubot/ -type f -perm 600 -exec chmod 644 {} \;')

def main():
    ''' Main function '''

    #
    # Step 1
    #
    # Make sure we start from a clean environment and that
    # we have a sane umask.
    #

    #
    # If we don't run the program as root we produce Archive.bom
    # with wrong ownership and we don't want that to happen.
    #
    if os.getuid() != 0:
        sys.exit('You must run this program as root')

    os.umask(0022)

    if os.path.lexists('neubot-%s.pkg' % VERSION):
        shutil.rmtree('neubot-%s.pkg' % VERSION)
    if os.path.lexists('neubot'):
        shutil.rmtree('neubot')

    if os.path.lexists('Privacy/build'):
        shutil.rmtree('Privacy/build')

    if not os.path.exists('../dist'):
        os.mkdir('../dist')
    if not os.path.exists('../dist/macos'):
        os.mkdir('../dist/macos')

    #
    # Step 2
    #
    # Create package by copying from the package skeleton
    #

    shutil.copytree(
                    'neubot-pkg',
                    'neubot-%s.pkg' % VERSION,
                    ignore=IGNORER
                   )

    #
    # Step 3
    #
    # Creates and populates the directory that will be copied
    # to /usr/local/share/neubot.  In particular, put there
    # Neubot sources; compile them; and copy all the scripts
    # we need to have in there.
    #

    shutil.copytree(
                    '../neubot-%s/neubot' % VERSION,
                    'neubot/%s/neubot' % NUMERIC_VERSION,
                    ignore=IGNORER
                   )

    shutil.copytree(
                    '../neubot-%s/mod_dash' % VERSION,
                    'neubot/%s/mod_dash' % NUMERIC_VERSION,
                    ignore=IGNORER
                   )

    #
    # Copy scripts.  Note that start.sh and the plist file
    # must be in /usr/local/share/neubot while the rest goes
    # into the version-specific directory.
    #

    shutil.copy('basedir-skel/start.sh', 'neubot')

    shutil.copy('basedir-skel/org.neubot.plist', 'neubot')

    shutil.copy('basedir-skel/versiondir-skel/cmdline.sh',
                'neubot/%s' % NUMERIC_VERSION)

    shutil.copy('basedir-skel/versiondir-skel/start.sh',
                'neubot/%s' % NUMERIC_VERSION)

    shutil.copy('basedir-skel/versiondir-skel/prerun.sh',
                'neubot/%s' % NUMERIC_VERSION)

    shutil.copy('basedir-skel/versiondir-skel/uninstall.sh',
                'neubot/%s' % NUMERIC_VERSION)

    shutil.copy('../pubkey.pem', 'neubot/%s' % NUMERIC_VERSION)

    shutil.copy('basedir-skel/versiondir-skel/org.neubot.notifier.plist',
                'neubot/%s' % NUMERIC_VERSION)

    # Copy Neubot.app too

    shutil.copytree(
                    'basedir-skel/versiondir-skel/Neubot-app',
                    'neubot/%s/Neubot.app' % NUMERIC_VERSION,
                    ignore=IGNORER,
                   )

    # Add manual page(s)

    shutil.copy('../neubot-%s/UNIX/man/man1/neubot.1' % VERSION,
                'neubot/%s' % NUMERIC_VERSION)

    #
    # Step 4
    #
    # Fix the permissions and ownership of what we have created so far,
    # so we put sensible stuff into the autoupdate tarball.
    #

    _fixup_perms()

    #
    # Step 5
    #
    # Create, checksum, and sign the tarball that contains the updated
    # code for auto-updating clients.
    #

    tarball = '../dist/macos/%s.tar.gz' % NUMERIC_VERSION
    sha256sum = '../dist/macos/%s.tar.gz.sha256' % NUMERIC_VERSION
    sig = '../dist/macos/%s.tar.gz.sig' % NUMERIC_VERSION

    # Create tarball

    arch = tarfile.open(tarball, 'w:gz')
    os.chdir('neubot')
    arch.add('%s' % NUMERIC_VERSION)
    arch.close()
    os.chdir(MACOSDIR)

    # Calculate sha256sum

    filep = open(tarball, 'rb')
    hashp = hashlib.new('sha256')
    content = filep.read()
    hashp.update(content)
    digest = hashp.hexdigest()
    filep.close()

    # Write sha256sum

    filep = open(sha256sum, 'wb')
    filep.write('%s  %s\n' % (digest, os.path.basename(tarball)))
    filep.close()

    # Sign the tarball

    os.chdir('../dist/macos')
    _sign(os.path.basename(sig), os.path.basename(tarball))
    os.chdir(MACOSDIR)

    #
    # Step 6
    #
    # Compile the sources at VERSIONDIR. We compile the sources after
    # we created the auto-update tarball, because we don't ship the
    # .pyc files into the auto-update tarball.
    #

    compileall.compile_dir('neubot/%s' % NUMERIC_VERSION)

    #
    # Step 7
    #
    # Add the okfile to VERSIONDIR. We add the okfile after we created
    # the auto-update tarball, because the okfile MUST NOT go inside the
    # auto-update tarball.
    #

    filep = open('neubot/%s/.neubot-installed-ok' % NUMERIC_VERSION, 'w')
    filep.close()

    #
    # Step 8
    #
    # Fix again the permission and ownership, to include also the
    # files that we created in step 6 and 7.
    #

    _fixup_perms()

    #
    # Step 9
    #
    # Create the archive that contains the stuff to install, and also
    # prepare the related bill of materials (BOM).
    #

    _call('pax -wzf %s -x cpio %s' %
       (
        'neubot-%s.pkg/Contents/Archive.pax.gz' % VERSION,
        'neubot'
       ))

    _call('mkbom %s %s' %
       (
        'neubot',
        'neubot-%s.pkg/Contents/Archive.bom' % VERSION,
       ))

    #
    # Step 10
    #
    # Stuff the .pkg directory into a .tar.gz, and sign the .tar.gz
    #

    path = '../dist/neubot-%s.pkg.tgz' % VERSION

    arch = tarfile.open(path, 'w:gz')
    arch.add('neubot-%s.pkg' % VERSION)
    arch.close()

    os.chdir("../dist")
    _sign(os.path.basename(path + ".sig"), os.path.basename(path))
    os.chdir(MACOSDIR)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit:
        raise
    except:
        traceback.print_exc()
        sys.exit(1)
