# -*- coding: utf-8 -*-
# Copyright (c) 2012, Bin Tan
# This file is distributed under the BSD Licence.
# See python-epub-builder-license.txt for details.

import os
import uuid
import shutil
import zipfile
import itertools
import mimetypes
import subprocess
from lxml import etree
from genshi.template import TemplateLoader


class TocMapNode:

    def __init__(self):
        self.playOrder = 0
        self.title = ""
        self.href = ""
        self.children = []
        self.depth = 0

    def assignPlayOrder(self):
        nextPlayOrder = [0]
        self.__assignPlayOrder(nextPlayOrder)

    def __assignPlayOrder(self, nextPlayOrder):
        self.playOrder = nextPlayOrder[0]
        nextPlayOrder[0] = self.playOrder + 1
        for child in self.children:
            child.__assignPlayOrder(nextPlayOrder)


class EpubItem:

    def __init__(self):
        self.id = ""
        self.srcPath = ""
        self.destPath = ""
        self.mimeType = ""
        self.html = ""


class EpubBook:

    def __init__(self):
        self.loader = TemplateLoader(os.path.join(
            os.path.split(os.path.realpath(__file__))[0], "templates"))
        self.rootDir = ""
        self.UUID = uuid.uuid1()

        self.lang = "en-US"
        self.title = ""
        self.creators = []
        self.metaInfo = []
        self.version = "3"

        self.imageItems = {}
        self.htmlItems = {}
        self.cssItems = {}

        self.coverImage = None
        self.titlePage = None
        self.tocPage = None

        self.spine = []
        self.guide = {}
        self.tocMapRoot = TocMapNode()
        self.lastNodeAtDepth = {0: self.tocMapRoot}

    def setVersion(self, version):
        self.version = version

    def setTitle(self, title):
        self.title = title

    def setLang(self, lang):
        self.lang = lang

    def addCreator(self, name, role="aut"):
        self.creators.append((name, role))

    def addMeta(self, metaName, metaValue, **metaAttrs):
        self.metaInfo.append((metaName, metaValue, metaAttrs))

    def getMetaTags(self):
        l = []
        for metaName, metaValue, metaAttr in self.metaInfo:
            beginTag = "<dc:%s" % metaName
            if metaAttr:
                for attrName, attrValue in metaAttr.iteritems():
                    beginTag += " %s='%s'" % (attrName, attrValue)
            beginTag += ">"
            endTag = "</dc:%s>" % metaName
            l.append((beginTag, metaValue, endTag))
        return l

    def getImageItems(self):
        return sorted(self.imageItems.values(), key=lambda x: x.id)

    def getHtmlItems(self):
        return sorted(self.htmlItems.values(), key=lambda x: x.id)

    def getCssItems(self):
        return sorted(self.cssItems.values(), key=lambda x: x.id)

    def getAllItems(self):
        return sorted(itertools.chain(self.imageItems.values(),
         self.htmlItems.values(), self.cssItems.values()), key=lambda x: x.id)

    def addImage(self, srcPath, destPath):
        item = EpubItem()
        item.id = "image_%d" % (len(self.imageItems) + 1)
        item.srcPath = srcPath
        item.destPath = destPath
        item.mimeType = mimetypes.guess_type(destPath)[0]
        assert item.destPath not in self.imageItems
        self.imageItems[destPath] = item
        return item

    def addHtmlForImage(self, imageItem):
        tmpl = self.loader.load(os.path.join("OEBPS", "image.html"))
        stream = tmpl.generate(book=self, item=imageItem)
        html = stream.render(
            "xhtml", doctype="xhtml11", drop_xml_decl=False)
        return self.addHtml("", "%s.html" % imageItem.destPath, html)

    def addHtml(self, srcPath, destPath, html):
        item = EpubItem()
        item.id = "html_%d" % (len(self.htmlItems) + 1)
        item.srcPath = srcPath
        item.destPath = destPath
        item.html = html
        item.mimeType = "application/xhtml+xml"
        assert item.destPath not in self.htmlItems
        self.htmlItems[item.destPath] = item
        return item

    def addCss(self, srcPath):
        item = EpubItem()
        item.id = "css_%d" % (len(self.cssItems) + 1)
        item.srcPath = srcPath
        item.destPath = os.path.join("css", os.path.split(srcPath)[-1])
        item.mimeType = "text/css"
        assert item.destPath not in self.cssItems
        self.cssItems[item.destPath] = item
        return item

    def addCover(self, srcPath):
        assert not self.coverImage
        _, ext = os.path.splitext(srcPath)
        destPath = os.path.join("images", "cover%s" % ext)
        self.coverImage = self.addImage(srcPath, destPath)
        #coverPage = self.addHtmlForImage(self.coverImage)
        #self.addSpineItem(coverPage, False, -300)
        #self.addGuideItem(coverPage.destPath, "Cover", "cover")

    def __makeTitlePage(self):
        assert self.titlePage
        if self.titlePage.html:
            return
        tmpl = self.loader.load(os.path.join("OEBPS", "title-page.html"))
        stream = tmpl.generate(book=self)
        self.titlePage.html = stream.render(
            "xhtml", doctype="xhtml11", drop_xml_decl=False)

    def addTitlePage(self, html=""):
        assert not self.titlePage
        self.titlePage = self.addHtml("", "title-page.html", html)
        self.addSpineItem(self.titlePage, True, -200)
        self.addGuideItem("title-page.html", "Title Page", "title-page")

    def __makeTocPage(self):
        assert self.tocPage
        tmpl = self.loader.load(os.path.join("OEBPS", "toc.html"))
        stream = tmpl.generate(book=self)
        self.tocPage.html = stream.render(
            "xhtml", doctype="xhtml11", drop_xml_decl=False)

    def addTocPage(self):
        assert not self.tocPage
        self.tocPage = self.addHtml("", "toc.html", "")
        self.addSpineItem(self.tocPage, False, -100)
        self.addGuideItem("toc.html", "Table of Contents", "toc")

    def getSpine(self):
        return sorted(self.spine)

    def addSpineItem(self, item, linear=True, order=None):
        assert item.destPath in self.htmlItems
        if order == None:
            order = (max(order for order, _, _ in 
                self.spine) if self.spine else 0) + 1
        self.spine.append((order, item, linear))

    def getGuide(self):
        return sorted(self.guide.values(), key=lambda x: x[2])

    def addGuideItem(self, href, title, type):
        assert type not in self.guide
        self.guide[type] = (href, title, type)

    def getTocMapRoot(self):
        return self.tocMapRoot

    def getTocMapHeight(self):
        return max(self.lastNodeAtDepth.keys())

    def addTocMapNode(self, href, title, depth=None, parent=None):
        node = TocMapNode()
        node.href = href
        node.title = title
        if parent == None:
            if depth == None:
                parent = self.tocMapRoot
            else:
                parent = self.lastNodeAtDepth[depth - 1]
        parent.children.append(node)
        node.depth = parent.depth + 1
        self.lastNodeAtDepth[node.depth] = node
        return node

    def makeDirs(self):
        for folder in ["META-INF", "OEBPS", 
            os.path.join("OEBPS", "css"), 
            os.path.join("OEBPS", "images")]:
            try:
                os.makedirs(os.path.join(self.rootDir, folder))
            except OSError:
                pass

    def __writeContainerXML(self):
        fout = open(
            os.path.join(self.rootDir, "META-INF", "container.xml"), "w")
        tmpl = self.loader.load(os.path.join("META-INF", "container.xml"))
        stream = tmpl.generate()
        fout.write(stream.render("xml"))
        fout.close()

    def __writeTocNCX(self):
        self.tocMapRoot.assignPlayOrder()
        fout = open(os.path.join(self.rootDir, "OEBPS", "toc.ncx"), "w")
        tmpl = self.loader.load(os.path.join("OEBPS", "toc.ncx"))
        stream = tmpl.generate(book = self)
        fout.write(stream.render("xml").encode("utf-8"))
        fout.close()

    def __writeContentOPF(self):
        fout = open(os.path.join(self.rootDir, "OEBPS", "content.opf"), "w")
        tmpl = self.loader.load(os.path.join("OEBPS", "content.opf"))
        stream = tmpl.generate(book=self).render("xml")
        fout.write(stream.encode("utf-8"))
        fout.close()

    def __writeItems(self):
        for item in self.getAllItems():
            print item.id, item.destPath
            if item.html:
                fout = open(
                    os.path.join(self.rootDir, "OEBPS", item.destPath), "w")
                fout.write(item.html.encode("utf-8"))
                fout.close()
            else:
                shutil.copyfile(item.srcPath, os.path.join(
                    self.rootDir, "OEBPS", item.destPath))

    def __writeMimeType(self):
        fout = open(os.path.join(self.rootDir, "mimetype"), "w")
        fout.write("application/epub+zip")
        fout.close()

    @staticmethod
    def __listManifestItems(contentOPFPath):
        tree = etree.parse(contentOPFPath)
        return tree.xpath("//manifest/item/@href", 
            namespaces={"opf": "http://www.idpf.org/2007/opf"})

    @staticmethod
    def createArchive(rootDir, outputPath):
        fout = zipfile.ZipFile(outputPath, "w")
        cwd = os.getcwd()
        os.chdir(rootDir)
        fout.write("mimetype", compress_type=zipfile.ZIP_STORED)
        fileList = []
        fileList.append(os.path.join("META-INF", "container.xml"))
        fileList.append(os.path.join("OEBPS", "content.opf"))
        for itemPath in EpubBook.__listManifestItems(
            os.path.join("OEBPS", "content.opf")):
            fileList.append(os.path.join("OEBPS", itemPath))
        for filePath in fileList:
            fout.write(filePath, compress_type=zipfile.ZIP_DEFLATED)
        fout.close()
        os.chdir(cwd)

    @staticmethod
    def checkEpub(checkerPath, epubPath):
        subprocess.call(["java", "-jar", checkerPath, epubPath], shell=True)

    def createBook(self, rootDir):
        if self.titlePage:
            self.__makeTitlePage()
        if self.tocPage:
            self.__makeTocPage()
        self.rootDir = rootDir
        self.makeDirs()
        self.__writeMimeType()
        self.__writeItems()
        self.__writeContainerXML()
        self.__writeContentOPF()
        if self.version == "2":
            self.__writeTocNCX()
