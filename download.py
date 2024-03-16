# Orthanc plugin for mammography
# Copyright (C) 2024 Edouard Chatzopoulos and Sebastien Jodogne,
# ICTEAM UCLouvain, Belgium
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import hashlib
import io
import os
import requests
import sys

def get(target, url, expected_size, expected_md5):
    print('Downloading: %s' % url)

    if os.path.isfile(target):
        with open(target, 'rb') as f:
            content = f.read()

            if (len(content) == expected_size and
                hashlib.md5(content).hexdigest() == expected_md5):
                print('  File already downloaded')
                return
            else:
                raise Exception('Target file already exists with bad content, please remove it: %s' % target)

    r = requests.get(url, stream = True)
    r.raise_for_status()

    content_length = int(r.headers['Content-Length'])
    if content_length != expected_size:
        raise Exception('Bad file size on the server: %d (actual) vs. %d (expected)' % (content_length, expected_size))

    bar_width = 30

    with io.BytesIO() as f:
        progress = 0

        for chunk in r.iter_content(chunk_size = 1024 * 1024):
            f.write(chunk)

            progress += len(chunk)
            percent = float(progress) / float(content_length)
            sys.stdout.write('\r')
            sys.stdout.write('  Completed: [{:{}}] {:>3}%'
                             .format('=' * round(percent * float(bar_width)),
                                     bar_width, round(percent * 100.0)))
            sys.stdout.flush()

        sys.stdout.write('\n')
        sys.stdout.flush()

        f.seek(0)
        content = f.read()

    if len(content) != expected_size:
        raise Exception('Server has not returned the expected number of bytes: %d (actual) vs. %d (expected)' % (len(content), expected_size))

    actual_md5 = hashlib.md5(content).hexdigest()
    if actual_md5 != expected_md5:
        raise Exception('Bad MD5 checksum: %s (actual) vs. %s (expected)' % (actual_md5, expected_md5))

    with open(target, 'wb') as f:
        f.write(content)
