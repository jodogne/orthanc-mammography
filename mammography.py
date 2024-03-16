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


##
## Initialize the virtual environment for pytorch.
## DO NOT add other "import" in this section!
##

import sys
import json
import orthanc

config = json.loads(orthanc.GetConfiguration()).get('Mammography', {})
venv = config.get('VirtualEnv')

if venv != None:
    # https://orthanc.uclouvain.be/book/plugins/python.html#working-with-virtual-environments
    sys.path.insert(0, venv)


##
## Install the Stone Web viewer
##

STONE_VERSION = '2024-03-15-StoneWebViewer-DICOM-SR'
VIEWER_PREFIX = '/mammography-viewer/'

import os
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
VIEWER_DIR = os.path.join(SCRIPT_DIR, 'viewer')

sys.path.append(os.path.join(SCRIPT_DIR, '..'))
import download

os.makedirs(VIEWER_DIR, exist_ok = True)

download.get(os.path.join(VIEWER_DIR, '%s.zip' % STONE_VERSION),
             'https://github.com/jodogne/orthanc-mammography/raw/master/viewer/%s.zip' % STONE_VERSION,
             4742571, 'de952da6fc74a9d4b78ca5064a6a7318')

import zipfile
stone_assets = zipfile.ZipFile(os.path.join(VIEWER_DIR, '%s.zip' % STONE_VERSION))

MIME_TYPES = {
    '.css'  : 'text/css',
    '.gif'  : 'image/gif',
    '.html' : 'text/html',
    '.jpeg' : 'image/jpeg',
    '.js'   : 'text/javascript',
    '.png'  : 'image/png',
}

def serve_stone_web_viewer(output, uri, **request):
    if not uri.startswith(VIEWER_PREFIX):
        output.SendHttpStatusCode(404)
    elif request['method'] != 'GET':
        output.SendMethodNotAllowed('GET')
    else:
        try:
            path = '%s/%s' % (STONE_VERSION, uri[len(VIEWER_PREFIX):])
            extension = os.path.splitext(path) [1]
            if not extension in MIME_TYPES:
                mime = 'application/octet-stream'
            else:
                mime = MIME_TYPES[extension]

            with stone_assets.open(path) as f:
                output.AnswerBuffer(f.read(), mime)
        except:
            output.SendHttpStatusCode(500)


orthanc.RegisterRestCallback('%s(.*)' % VIEWER_PREFIX, serve_stone_web_viewer)


##
## Load the deep learning model
##

import highdicom
import io
import os
import pydicom

sys.path.append(os.path.join(SCRIPT_DIR, '..'))
import model
import dicom_sr

orthanc.LogWarning('Loading the RetinaNet model for mammography')
my_retina_net = model.load_retina_net()


##
## Install the Orthanc Explorer extension
##

with open(os.path.join(SCRIPT_DIR, 'OrthancExplorer.js'), 'r') as f:
    orthanc.ExtendOrthancExplorer(f.read())

def execute_inference(output, uri, **request):
    if request['method'] != 'POST':
        output.SendMethodNotAllowed('POST')
    else:
        body = json.loads(request['body'])

        f = orthanc.GetDicomForInstance(body['instance'])
        dicom = pydicom.dcmread(io.BytesIO(f))

        if len(dicom.pixel_array.shape) != 2:
            orthanc.LogError('Not a graylevel instance: %s' % body['instance'])
            output.SendHttpStatusCode(400)
        else:
            result = dicom_sr.apply(my_retina_net, dicom, minimum_score=0.2)

            with io.BytesIO() as f:
                pydicom.dcmwrite(f, result)
                f.seek(0)
                content = f.read()

            output.AnswerBuffer(orthanc.RestApiPost('/instances', content), 'application/json')

orthanc.RegisterRestCallback('/mammography-apply', execute_inference)
