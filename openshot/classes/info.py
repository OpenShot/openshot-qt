#	OpenShot Video Editor is a program that creates, modifies, and edits video files.
#
#	This file is part of OpenShot Video Editor (http://launchpad.net/openshot/).
#   Copyright (C) 2009  TJ, Jonathan Thomas
#
#	OpenShot Video Editor is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	OpenShot Video Editor is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with OpenShot Video Editor.  If not, see <http://www.gnu.org/licenses/>.

VERSION             = "2.0.0"
DATE                = "20130602800000"
NAME                = 'openshot'
GPL_VERSION         = '3'
SUPPORTED_LANGUAGES = ['English', 'Dutch', 'French', 'German', 'Italian', 'Portuguese', 'Spanish', 'Swedish']

# names of all contributers, using 'u' for unicode encoding
AF   = {'name': u'Andy Finch', 'email': 'we.rocked.in79@gmail.com'}
HMC  = {'name': u'Helen McCall', 'email': 'wildnfree@blueyonder.co.uk'}
JT   = {'name': u'Jonathan Thomas', 'email': 'jonathan.oomph@gmail.com'}
OG   = {'name': u'Olivier Girard', 'email': 'eolinwen@gmail.com'}
TJ   = {'name': u'TJ', 'email': 'ubuntu@tjworld.net'}
MA   = {'name': u'Mael Lavault', 'email': 'moimael@neuf.fr'}
IM   = {'name': u'itomailg', 'email': 'itomailg@gmail.com'}
JS   = {'name': u'jEsuSdA', 'email': 'info@jesusda.com'}
FF   = {'name': u'Francesco Fantoni', 'email': 'francesco@hv-a.com'}
EB   = {'name': u'Emil Berg', 'email': 'emil_berg91@hotmail.com'}

#credits
CREDITS = {
    'code'          : [JT, AF, TJ, OG, MA, IM, FF, EB],
    'artwork'       : [JT, JS],
    'documentation' : [OG, JT, HMC],
    'translation'   : [HMC, OG],
}

SETUP   = {
    'name'              : NAME,
    'version'           : VERSION,
    'author'            : JT['name'] + ' and others',
    'author_email'      : JT['email'],
    'maintainer'        : JT['name'],
    'maintainer_email'  : JT['email'],
    'url'               : 'http://www.openshotvideo.com/',
    'license'           : 'GNU GPL v.' + GPL_VERSION,
	'description'	   : 'Create and edit videos and movies',
	'long_description'  : "Create and edit videos and movies\n OpenShot Video Editor is a free, open-source, non-linear video editor.  It\n can create and edit videos and movies using many popular video, audio, and\n image formats.  Create videos for YouTube, Flickr, Vimeo, Metacafe, iPod,\n Xbox, and many more common formats!\n .\n Features include:\n  * Multiple tracks (layers)\n  * Compositing, image overlays, and watermarks\n  * Support for image sequences (rotoscoping)\n  * Key-frame animation\n  * Video and audio effects (chroma-key)\n  * Transitions (lumas and masks)\n  * 3D animation (titles and simulations)\n  * Upload videos (YouTube and Vimeo supported)",
		 

# see http://pypi.python.org/pypi?%3Aaction=list_classifiers
    'classifiers'       : [          
                           'Development Status :: 5 - Production/Stable',
                           'Environment :: X11 Applications',
                           'Environment :: X11 Applications :: GTK',
                           'Intended Audience :: End Users/Desktop',
                           'License :: OSI Approved :: GNU General Public License (GPL)',
                           'Operating System :: OS Independent',
                           'Operating System :: POSIX :: Linux',
                           'Programming Language :: Python',
                           'Topic :: Artistic Software',
                           'Topic :: Multimedia :: Video :: Non-Linear Editor',] +
                          ['Natural Language :: ' + language for language in SUPPORTED_LANGUAGES
                          ],
}

