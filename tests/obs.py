#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# (C) 2014 tchvatal@suse.cz, openSUSE.org
# Distribute under GPLv2 or later

import os
import sys
import contextlib
import unittest
import httpretty
import difflib
import subprocess
import tempfile
import xml.etree.ElementTree as ET
# mock is part of python3.3
try:
    import unittest.mock
except ImportError:
    import mock

from string import Template
import oscs
import osc
import re
import pprint
import posixpath

PY3 = sys.version_info[0] == 3

if PY3:
    string_types = str,
else:
    string_types = basestring,

# Here place all mockable functions
@contextlib.contextmanager
def mock_generate_ring_packages():
    with  mock.patch('oscs.StagingAPI._generate_ring_packages', return_value={
        'elem-ring-0': 'openSUSE:Factory:Rings:0-Bootstrap',
        'elem-ring-1': 'openSUSE:Factory:Rings:1-MinimalX'}):
        yield

class OBS:
    """
    Class trying to simulate a simple OBS
    """

    def __init__(self):
        """
        Initialize the configuration and create basic OBS instance
        """

        # Make osc happy about config file
        oscrc = os.path.join(self._get_fixtures_dir(), 'oscrc')
        osc.core.conf.get_config(override_conffile=oscrc,
                                 override_no_keyring=True,
                                 override_no_gnome_keyring=True)
        os.environ['OSC_CONFIG'] = oscrc

        # (Re)set configuration
        self.reset_config()

    def reset_config(self):
        """
        Resets whole OBS class
        """
        # Initialize states
        self._set_init_data()
        # Setup callbacks
        self._clear_responses()

    def _set_init_data(self):
        """
        Resets states
        """
        # Initial request data
        self.requests_data = { '123': { 'request': 'new', 'review': 'accepted',
                                        'who': 'Admin', 'by': 'group', 'id': '123',
                                        'by_who': 'opensuse-review-team',
                                        'package': 'gcc' },
                               '321': { 'request': 'review', 'review': 'new',
                                        'who': 'Admin', 'by': 'group', 'id': '321',
                                        'by_who': 'factory-staging',
                                        'package': 'puppet' },
                               '333': { 'request': 'review', 'review': 'new',
                                        'who': 'Admin', 'by': 'project', 'id': '333',
                                        'by_who': 'openSUSE:Factory:Staging:B',
                                        'package': 'wine' }
                             }
        self.st_project_data = { 'A': { 'project': 'openSUSE:Factory:Staging:A',
                                        'title': '', 'description': '' },
                                 'B': { 'project': 'openSUSE:Factory:Staging:B',
                                        'title': 'wine',
                                        'description': 'requests:\n- {id: 333, package: wine}' }
                               }
        self.links_data = { 'openSUSE:Factory:Staging:B/wine':
                                    { 'prj': 'openSUSE:Factory:Staging:B',
                                      'pkg': 'wine', 'devprj': 'devel:wine' }
                                    }
        self.pkg_data = { 'home:Admin/gcc':
                                    { 'rev': '1', 'vrev': '1', 'name': 'gcc',
                                      'srcmd5': 'de7a9f5e3bedb01980465f3be3d236cb' }
                                    }
 
    def _clear_responses(self):
        """
        Resets predefined responses
        """
        self.responses = { 'DELETE': {}, 'GET': {}, 'PUT': {}, 'POST': {}, 'ALL': {} }

        # Add methods to manipulate reviews
        self._request_review()
        # Add methods to search requests and projects
        self._search()
        # Add methods to work with project metadata
        self._project_meta()
        # Add linked packages
        self._link_sources()
        # Add packages
        self._pkg_sources()

    def _pretty_callback(self, request, uri, headers, exception=True):
        """
        Custom callback for HTTPretty.

        It mocks requests and replaces calls with either xml, content of file,
        function call or first item in array of those.

        :param request: request as provided to callback function by HTTPretty
        :param uri: uri as provided to callback function by HTTPretty
        :param headers: headers as provided to callback function by HTTPretty
        """

        # Get path
        path = re.match( r'.*localhost([^?]*)(\?.*)?',uri).group(1)
        reply = None
        # Try to find a fallback
        if self.responses['ALL'].has_key(path):
            reply = self.responses['ALL'][path]
        # Try to find a specific method
        if self.responses[request.method].has_key(path):
            reply = self.responses[request.method][path]
        # We have something to reply with
        if reply:
            # It's a list, so take the first
            if isinstance(reply, list):
                reply = reply.pop(0)
            # It's string
            if isinstance(reply, string_types):
                # It's XML
                if reply.startswith('<'):
                    return (200, headers, reply)
                # It's fixture
                else:
                    return (200, headers, self._get_fixture_content(reply))
            # All is left is callback function
            else:
                return (200, headers, reply(self.responses, request, uri))
        # No possible response found
        else:
            if len(path) == 0:
                path = uri
            if len(path) > 1:
                ret = self._pretty_callback(request, 'https://localhost' + posixpath.dirname(path), headers, False)
            if exception:
                raise BaseException("No tests/obs.pyresponse for {0} on {1} provided".format(request.method,path))
            else:
                return None

    def _project_meta(self):
        # Load template
        tmpl = Template(self._get_fixture_content('staging-project-meta.xml'))

        def project_meta_change(responses, request, uri):
            path = re.match( r'.*localhost([^?]*)(\?.*)?',uri).group(1)
            self.responses['GET'][path] = request.body
            return self.responses['GET'][path]

        # Register methods for all requests
        for pr in self.st_project_data:
            # Static response for gets (just filling template from local data)
            self.responses['GET']['/source/openSUSE:Factory:Staging:' + pr + '/_meta'] = tmpl.substitute(self.st_project_data[pr])
            # Interpret other requests
            self.responses['ALL']['/source/openSUSE:Factory:Staging:' + pr + '/_meta'] = project_meta_change

    def _request_review(self):
        """
        Register requests methods
        """

        # Load template
        tmpl = Template(self._get_fixture_content('request_review.xml'))

        # What happens when we try to change the review
        def review_change(responses, request, uri):
            rq_id = re.match( r'.*/([0-9]+)',uri).group(1)
            args = self.requests_data[rq_id]
            # Adding review
            if request.querystring.has_key(u'cmd') and request.querystring[u'cmd'] == [u'addreview']:
                self.requests_data[rq_id]['request'] = 'review'
                self.requests_data[rq_id]['review']  = 'new'
            # Changing review
            if request.querystring.has_key(u'cmd') and request.querystring[u'cmd'] == [u'changereviewstate']:
                self.requests_data[rq_id]['request'] = 'new'
                self.requests_data[rq_id]['review']  = str(request.querystring[u'newstate'][0])
            # Project review
            if request.querystring.has_key(u'by_project'):
                self.requests_data[rq_id]['by']      = 'project'
                self.requests_data[rq_id]['by_who']  = str(request.querystring[u'by_project'][0])
            # Group review
            if request.querystring.has_key(u'by_group'):
                self.requests_data[rq_id]['by']      = 'group'
                self.requests_data[rq_id]['by_who']  = str(request.querystring[u'by_group'][0])
            responses['GET']['/request/' + rq_id]  = tmpl.substitute(self.requests_data[rq_id])
            return responses['GET']['/request/' + rq_id]

        # Register methods for all requests
        for rq in self.requests_data:
            # Static response for gets (just filling template from local data)
            self.responses['GET']['/request/' + rq] = tmpl.substitute(self.requests_data[rq])
            # Interpret other requests
            self.responses['ALL']['/request/' + rq] = review_change

    def _pkg_sources(self):
        def pkg_source(responses, request, uri):
            key = str(re.match( r'.*/source/([^?]+)(\?.*)?',uri).group(1))
            return '<directory name="{0}" rev="{1}" vrev="{2}" srcmd5="{3}"/>'.format(
                        self.pkg_data[key]['name'],
                        self.pkg_data[key]['rev'],
                        self.pkg_data[key]['vrev'],
                        self.pkg_data[key]['srcmd5']
                   )
        for pkg in self.pkg_data:
            self.responses['GET']['/source/' + pkg] = pkg_source

    def _link_sources(self):
        # Load template
        tmpl = Template(self._get_fixture_content('linksource.xml'))

        def delete_link(responses, request, uri):
            key = re.match( r'.*/source/([^?]+)(\?.*)?',uri).group(1)
            del self.responses['GET']['/source/' + str(key)]
            del self.links_data[str(key)]
            return "Ok"

        def create_empty(responses, request, uri):
            key = re.match( r'.*/source/(.+)/_meta',uri).group(1)
            self.links_data[str(key)] = {}
            return "Ok"

        def create_link(responses, request, uri):
            key = re.match( r'.*/source/(.+)/_link',uri).group(1)
            match = re.match( r'(.+)/(.+)', key)
            xml = ET.fromstring(str(request.body))
            self.links_data[str(key)] = { 'prj': match.group(1), 'pkg': match.group(2),
                                          'devprj': xml.get('project')
                                        }
            return "Ok"

        # Register methods for requests
        for link in self.links_data:
            self.responses['GET']['/source/' + link] = tmpl.substitute(self.links_data[link])
            self.responses['DELETE']['/source/' + link] = delete_link

        # Register method for package creation
        for pr in self.st_project_data:
            for rq in self.requests_data:
                self.responses['PUT']['/source/openSUSE:Factory:Staging:' + pr + '/' + self.requests_data[rq]['package'] + '/_meta'] = create_empty
                self.responses['PUT']['/source/openSUSE:Factory:Staging:' + pr + '/' + self.requests_data[rq]['package'] + '/_link'] = create_link

    def _search(self):
        """
        Allows searching for requests
        """
        def request_search(responses, request, uri):
            # Searching for requests that has open review for staging group
            if request.querystring.has_key(u'match') and request.querystring[u'match'][0] == u"state/@name='review' and review[@by_group='factory-staging' and @state='new']":
                rqs = []
                # Itereate through all requests
                for rq in self.requests_data:
                    # Find the ones matching the condition
                    if self.requests_data[rq]['request'] == 'review' and self.requests_data[rq]['review'] == 'new' and self.requests_data[rq]['by'] == 'group' and self.requests_data[rq]['by_who'] == 'factory-staging':
                        rqs.append(rq)
                # Create response
                ret_str  = '<collection matches="' + str(len(rqs)) + '">'
                for rq in rqs:
                    ret_str += responses['GET']['/request/' + rq]
                ret_str += '</collection>'
                return ret_str
            # We are searching for something else, we don't know the answer
            raise BaseException("No search results defined for " + pprint.pformat(request.querystring))

        def id_project_search(responses, request, uri):
            # Searching for project
            if request.querystring.has_key(u'match') and request.querystring[u'match'][0] == u"starts-with(@name,\'openSUSE:Factory:Staging:\')":
                ret_str = '<collection matches="' + str(len(self.st_project_data)) + '">\n'
                # Itereate through all requests
                for prj in self.st_project_data:
                    ret_str += '   <project name="openSUSE:Factory:Staging:' + prj + '"/>\n'
                ret_str += '</collection>'
                return ret_str
            # We are searching for something else, we don't know the answer
            raise BaseException("No search results defined for " + pprint.pformat(request.querystring))
        self.responses['GET']['/search/request'] = request_search
        self.responses['GET']['/search/project/id'] = id_project_search

    def register_obs(self):
        """
        Register custom callback for HTTPretty
        """
        httpretty.register_uri(httpretty.DELETE,re.compile(r'/.*localhost.*/'),body=self._pretty_callback)
        httpretty.register_uri(httpretty.GET,re.compile(r'/.*localhost.*/'),body=self._pretty_callback)
        httpretty.register_uri(httpretty.PUT,re.compile(r'/.*localhost.*/'),body=self._pretty_callback)
        httpretty.register_uri(httpretty.POST,re.compile(r'/.*localhost.*/'),body=self._pretty_callback)
        self.reset_config()
        # Initiate the api with mocked rings
        with mock_generate_ring_packages():
            self.api = oscs.StagingAPI('https://localhost')

    def _get_fixtures_dir(self):
        """
        Return path for fixtures
        """
        return os.path.join(os.getcwd(), 'tests/fixtures')

    def _get_fixture_path(self, filename):
        """
        Return path for fixture
        """
        return os.path.join(self._get_fixtures_dir(), filename)

    def _get_fixture_content(self, filename):
        """
        Return content of fixture
        """
        response = open(self._get_fixture_path(filename), 'r')
        content = response.read()
        response.close()
        return content

