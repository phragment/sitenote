#!/usr/bin/env python3

# Copyright 2017-2018 Thomas Krug
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import configparser
import io
import os
import re
import shutil
import sys

import hashlib
import uuid
from datetime import datetime

import docutils
import docutils.core

from docutils.parsers.rst import Directive
import docutils.nodes
from docutils.parsers.rst import directives


# TODO
# - images
#  strip big image exif
#  create thumbnails
# - cache control? (.htaccess)

head = '''<head>
<link rel="shortcut icon" href="/favicon.ico" type="image/ico" />
<meta name="viewport" content="width=device-width, initial-scale=1" />'''


class Overview(Directive):

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = False

    def run(self):
        #print("directive overview:", self.arguments)
        # get current dir
        d = self.arguments[0]

        art = crawl(d)

        # sort by date
        art = sorted(art, key=lambda k: k["date"], reverse=True)

        # create feed
        rss(d, art)

        nodes = []
        for a in art:
            entry = docutils.nodes.section()

            title = docutils.nodes.title()
            link = docutils.nodes.reference()
            link += docutils.nodes.Text(a["title"])
            link["refuri"] = a["link"]
            title += link
            entry += title

            if a["desc"]:
                for (i, child) in enumerate(a["desc"].children):
                    if child.tagname == "title":
                        del a["desc"].children[i]
                entry += a["desc"]

            nodes.append(entry)

        return nodes


def crawl(d):
    infos = []
    for e in os.listdir(d):
        fp = os.path.join(d, e)
        if os.path.isdir(fp):
            fp = os.path.join(fp, "index.rst")
            rst_f = open(fp, "r")
            rst = rst_f.read()
            rst_f.close()
            dtree = get_dtree(rst)
            info = get_info(dtree)
            info["link"] = fp
            infos.append(info)
    return infos


def rss(d, articles):

    # create atom 1.0 feed
    html_rss = '<link rel="alternate" type="application/atom+xml" href="{}" title="{}" />'

    global head
    #head += "\n" + html_rss.format("/" + d + "/feed.xml", _g_conf["title"] + " - Feed")
    head += "\n" + html_rss.format("/feed.xml", _g_conf["title"] + " - Feed")


    rss_head = """<feed xmlns="http://www.w3.org/2005/Atom">

    <link rel="self" type="application/atom+xml" href="{}"/>
    <title>{}</title>
    <id>{}</id>
    <updated>{}</updated>
    """

    rss_tail = "\n</feed>"

    # no content element, full text in summary for compatibility
    rss_entry = """
    <entry>
        <title>{}</title>
        <link href="{}" />
        <id>{}</id>
        <updated>{}</updated>
        <content type="xhtml">
            {}
        </content>
        <author>
            <name>{}</name>
        </author>
    </entry>
    """

    # atom date in RFC 3339 format
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    # atom id in urn syntax
    feed_id = uuid.UUID(hex=hashlib.md5(now.encode()).hexdigest()).urn
    #print(now, feed_id)

    #feed = rss_head.format("/" + d + "/feed.xml",
    feed = rss_head.format("/feed.xml",
                           _g_conf["title"],
                           feed_id, now)

    for article in articles:
        # TODO hash doctree?
        aid = ""
        with open(article["link"], "rb") as fa:
            aid = uuid.UUID(hex=hashlib.md5(fa.read()).hexdigest()).urn

        # TODO parse more date formats, use file timestamp if not available?
        date = article["date"]
        date = datetime.strptime(date, "%Y-%m-%d")
        date = date.strftime("%Y-%m-%dT%H:%M:%SZ")

        with open(article["link"], "r") as fa:
            rst = fa.read()

            dtree = get_dtree(rst)

            # TODO
            print(article["link"])
            print(d)
            #folder = "/".join(article["link"].split("/")[1:-1])
            folder = "/".join(article["link"].split("/")[:-1])
            print("folder: ", folder)
            dtree = dtree_prep_links(dtree, folder)

            dtree = dtree_prep(dtree, _g_conf)
            parts = get_html_parts(dtree)

            content = parts["html_body"]

            # TODO fix hack
            content = re.sub(r'<h1 class="title">.*</h1>', "", content)
            content = re.sub(r'<table class="docinfo"[\s\S]*</table>', "", content)
            content = re.sub(r'<p class="topic-title first">Abstract</p>', "", content)

            content = '<div xmlns="http://www.w3.org/1999/xhtml">{}</div>'.format(content)

        # TODO more link processing!
        feed += rss_entry.format(article["title"],
                                 article["link"].replace(".rst", ".html"),
                                 aid, date,
                                 content, article["author"])

    feed += rss_tail

    #with open(os.path.join(_g_dirout, d, "feed.xml"), "w") as f_feed:
    with open(os.path.join(_g_dirout, "feed.xml"), "w") as f_feed:
        f_feed.write(feed)

    return


def get_info(dtree):
    title = None
    date = ""
    desc = None
    author = ""

    for elem in dtree.traverse(siblings=True):
        if elem.tagname == "document":
            title = elem.get("title", "")
        if elem.tagname == "docinfo":
            for e in elem.children:
                if e.tagname == "date":
                    date = str( e.children[0] )
                if e.tagname == "author":
                    author = str( e.children[0] )
        if elem.tagname == "topic":
            # save dtree elements
            desc = elem

    data = {"title": title, "date": date, "desc": desc, "author": author}
    return data


def prep(conf):
    rst_fp = "header.rst"
    try:
        rst_f = open(rst_fp, "r")
    except FileNotFoundError:
        return None
    rst = rst_f.read()
    rst_f.close()
    header = render(rst, conf, "")
    header = re.search(r'<div class=\"document\">([\W\S]*)</div>', header, re.M).group(1)
    header = '<div class="header">' + header + "</div>"
    return header


def get_dtree(rst):
    try:
        with devnull():
            dtree = docutils.core.publish_doctree(rst)
    except docutils.utils.SystemMessage as e:
        print("error parsing rst")
        print(e)
        return None
    return dtree


def render(rst, conf, header):

    args = {
        "stylesheet_path": "",
        "stylesheet": "/default.css",
        "embed_stylesheet": False
    }

    # abs
    if args["stylesheet"].startswith("/"):
        args["stylesheet"] = conf["root"] + args["stylesheet"]

    dtree = get_dtree(rst)
    #print(dtree)
    dtree = dtree_prep(dtree, conf)

    try:
        with devnull():
            html = docutils.core.publish_from_doctree(dtree,
                       writer_name="html4css1",
                       #settings=None,
                       settings_overrides=args)
    except docutils.utils.SystemMessage as e:
        print("error generating html")
        print(e)
        return None
    except AttributeError as e:
        print("error generating html")
        print(e)
        return None

    html = html.decode()
    html = re.sub(r'<head>', head, html)

    if header:
        html = re.sub(r'<body>', "<body>" + header, html)

    # TODO can this be moved to dtree preparation?
    # open image links and external links in new tab
    lines = html.split("\n")
    html = ""
    for line in lines:
        #print(line)
        if re.search(r'<a.*href', line):
            #print(line)
            link = re.search(r'<a.*href=\"(.*)\".*a>', line).group(1)
            # TODO add list ["http", "https", "ftp", "ftps"]
            if link.startswith("http"):
                line = re.sub("href", 'target="_blank" href', line)
            if re.search(r'<img.*src', line):
                line = re.sub("href", 'target="_blank" href', line)
        html = html + "\n" + line

    return html


def dtree_prep(dtree, conf):

    for elem in dtree.traverse(siblings=True):
        if elem.tagname == "reference":
            try:
                refuri = elem["refuri"]
            except KeyError:
                continue

            if refuri.endswith(".rst"):
                elem["refuri"] = refuri.replace(".rst", ".html")

            # abs
            if refuri.startswith("/"):
                elem["refuri"] = conf["root"] + elem["refuri"]


        if elem.tagname == "image":
            try:
                uri = elem["uri"]
            except KeyError:
                continue

            # abs
            if uri.startswith("/"):
                elem["uri"] = conf["root"] + uri

        if elem.tagname == "document":
            title = elem.get("title", "")
            if title:
                elem["title"] = conf["title"] + " - " + elem["title"]
            else:
                elem["title"] = conf["title"]

        # TODO
        # if image and .tmb exists
        # wrap in reference

    return dtree


def dtree_prep_links(dtree, folder):
    for elem in dtree.traverse(siblings=True):
        if elem.tagname == "reference":
            try:
                refuri = elem["refuri"]
            except KeyError:
                continue
            if "://" in refuri:
                continue
            if refuri.startswith("/"):
                elem["refuri"] = "/" + folder + "/" + refuri
            else:
                elem["refuri"] = folder + "/" + refuri

        if elem.tagname == "image":
            try:
                uri = elem["uri"]
            except KeyError:
                continue
            if uri.startswith("/"):
                elem["uri"] = "/" + folder + "/" + uri
            else:
                elem["uri"] = folder + "/" + uri

    return dtree


def get_html_parts(dtree):
    overrides = {"embed_stylesheet": False}
    try:
        with devnull():
            html, pub = docutils.core.publish_programmatically(
                    source_class=docutils.io.DocTreeInput,
                    source=dtree,
                    source_path=None,
                    destination_class=docutils.io.StringOutput,
                    destination=None,
                    destination_path=None,
                    reader=docutils.readers.doctree.Reader(), reader_name="",
                    parser=None, parser_name="restructuredtext",
                    writer=None, writer_name="html4css1",
                    settings=None, settings_spec=None,
                    settings_overrides=overrides,
                    config_section=None,
                    enable_exit_status=None)
    except (docutils.utils.SystemMessage, AttributeError) as e:
        print(e)
        return None
    parts = pub.writer.parts
    return parts


class devnull():
    def __init__(self):
        self.devnull = io.StringIO()

    def __enter__(self):
        return
        sys.stdout = self.devnull
        sys.stderr = self.devnull

    def __exit__(self, type, value, traceback):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


def mkdir(fp):

    # behaves like "mkdir -p"
    try:
        os.makedirs(os.path.dirname(fp))
    except FileExistsError:
        pass


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("dirrst", help="input", nargs="?", default="rst")
    parser.add_argument("dirout", help="output", nargs="?", default="www")
    args = parser.parse_args()

    dirrst = os.path.abspath(args.dirrst)
    dirout = os.path.abspath(args.dirout)


    # read config
    parser = configparser.ConfigParser()
    parser.read("sitenote.conf")
    conf = dict(parser["site"])
    print(conf)

    global _g_conf
    _g_conf = conf

    # FIXME
    dirout = dirout + conf["root"]

    global _g_dirout
    _g_dirout = dirout

    os.chdir(dirrst)

    #
    directives.register_directive("overview", Overview)

    header = prep(conf)

    for cd, subdirs, files in os.walk("./"):

        #print(cd, subdirs, files)

        for f in files:

            if f.startswith("."):
                continue

            if f.endswith(".rst"):

                print("")

                # rel
                rst_fp = os.path.join(cd, f)
                print("convert", rst_fp)
                rst_f = open(rst_fp, "r")
                rst = rst_f.read()
                rst_f.close()

                html = render(rst, conf, header)

                # abs
                html_fp = os.path.join(dirout, rst_fp[:-4] + ".html")
                html_fp = os.path.normpath(html_fp)

                #print(html_fp)

                mkdir(html_fp)

                html_f = open(html_fp, "w")
                html_f.write(html)
                html_f.close()

            else:

                src = os.path.join(cd, f)
                dst = os.path.join(dirout, src)
                dst = os.path.normpath(dst)

                mkdir(dst)
                shutil.copy(src, dst)

                # TODO
                # check if image and bigger than 800px
                # then save .tmb

