#!/usr/bin/env python
"""
FlickrShow

Create a slideshow sub-folder inside a flickrsync.py flickr mirror folder.  
Currently the slideshow is based on a modified version of the Responisive 
Image Gallery:

http://tympanus.net/codrops/2011/09/20/responsive-image-gallery/ 

Dependencies on the slideshow are minimal, it would be easy to plug in
different Javascript slide show templates - they all seem to function in
a similar way.

@author: Michael Hamilton

This code is GPL 3.0(GNU General Public License) ( http://www.gnu.org/copyleft/gpl.html )
Copyright (C) 2012: Michael Hamilton

Home: codeincluded.blogspot.com
"""
from __future__ import print_function
import os
import sys
import re
import copy
import datetime
import shutil
#try:
#    import xml.etree.cElementTree as ET
#except ImportError as error:
import xml.etree.ElementTree as ET

from PIL import Image
from optparse import OptionParser
from xml.sax.saxutils import escape
from operator import itemgetter

# UTC? -seems like that's what it is
FLICKR_TIME_ZERO = datetime.datetime(1970, 01, 01) 
INSERT_DESCRIPTION = True

class ESTemplate(object):
    """
    Create a slideshow folder based on a modified version of the Responisive Image Gallery
    http://tympanus.net/codrops/2011/09/20/responsive-image-gallery/

    The slideshow folder is created inside the mirror folder so that the entire
    hierarchy can be copied to a USB-drive or CDROM as a self contained slideshow.

    You could implement/subclass a similar class for other slide show templates.
    """
    
    def __init__(self, template_path, mirror_path, slide_show_name='HTML-SlideShow', replace=False):
        self.template_src_dir = template_path
        self.template = ET.ElementTree()
        self.template.parse(os.path.join(template_path,"template.html"))
        self.thumb_list = self.template.find('.//ul[@class="template-thumb-list"]')   
        self.thumb_item_proto = self.thumb_list.find('li[@class="template-thumb-item"]')
        self.thumb_list.remove(self.thumb_item_proto)
        self.dest_path  = os.path.join(mirror_path, slide_show_name)
        self.thumb_path = os.path.join(self.dest_path , "images", "thumbs")
        tmp = os.path.join(mirror_path, slide_show_name + ".thumbs.tmp")
        if os.path.exists(self.dest_path):
            if replace:
                if os.path.isdir(self.thumb_path):
                    shutil.move(self.thumb_path, tmp)
                shutil.rmtree(self.dest_path)
            else:
                print("Destination already exists - force replacement option not set.")
                print("Destination:", self.dest_path)
            
        shutil.copytree(self.template_src_dir, self.dest_path)                
        if os.path.isdir(tmp):
            shutil.rmtree(self.thumb_path)
            shutil.move(tmp, self.thumb_path)
    
    def _create_thumbnail(self, img_path):
        """ Create a thumnail and return it's location """
        imgfilename = img_path
        thumbnail_path = os.path.join(self.thumb_path, os.path.basename(img_path))
        if not os.path.exists(thumbnail_path):
            try:
                print("Creating: ", thumbnail_path)
                img = Image.open(imgfilename)
                img.thumbnail((128, 128), Image.ANTIALIAS)
                img.save(thumbnail_path, "JPEG")
            except IOError as error:
                print(imgfilename, thumbnail_path, error)
                # keep going - not fatal
        return thumbnail_path
        
    def add(self, img_id, imgfile_path, title, desc_elem):
        """ Add an image to the slideshow, create a thumbnail for it too. """
        imgfile_relative   = os.path.relpath(imgfile_path, self.dest_path)
        thumbnail_relative = os.path.relpath(self._create_thumbnail(imgfile_path), self.dest_path)   
        
        # Copy the templated list element
        new_elem = copy.deepcopy(self.thumb_item_proto)    
        
        # Populate the new element with the data for this image
        img = new_elem.find('.//img[@class="template-thumb-img"]')
        img.set('src', thumbnail_relative) # change to relative ref
        img.set('alt', img_id)
	if INSERT_DESCRIPTION:
            img.set('data-description', escape(title.strip()))
        img.set('data-large', imgfile_relative)

	if INSERT_DESCRIPTION:
            div = new_elem.find('.//div[@class="template-long-description"]')
            div.append(desc_elem)

        self.thumb_list.append(new_elem) 

    def finish(self):
        """ Call to finish the slideshow - writing out the index.html """
        index_path = os.path.join(self.dest_path,"index.html")
        with open(index_path, 'w') as index_file:
            index_file.write('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"\n"http://www.w3.org/TR/html4/strict.dtd">\n')
            self.template.write(index_file, encoding='UTF-8', method="html")

def create_html_description(desc):
    """
    Create a description element, not necessariliy specific to ESTemplate
    """
    try:
        filtered_desc = desc.replace('\n','<br/>')
        #print(id, long_desc)
        desc_item = ET.XML(('<span>' + filtered_desc + '</span>').encode('utf-8'))
        #desc_item = '<span>' + filtered_desc + '</span>'
        #ET.dump(desc_item)
        return desc_item
    except Exception as parse_problem:
        print("Exception with desc:", desc, file=sys.stderr)
        print(parse_problem, file=sys.stderr)
    return ET.XML('<span> -- </span>')

def read_image_data(mirrorpath):
    """ 
    Find all image xml description files and load images to show, only
    include a given image once (even though it might be in more than one set)
    
    Returns: list of tuples, each being
        (img_id, title, desc, dirpath, name_of_set, latlon, when_taken)
    """
    img_list = []
    already_showing = {}
    for (dirpath, dirnames, files) in os.walk(mirrorpath):
        for filename in files:
            if re.match('[0-9]+[.]xml', filename):
                #print( filename)
                img_info = ET.ElementTree()
                img_info.parse(os.path.join(dirpath, filename))
                img_id = img_info.getroot().get('id')
                if not img_id in already_showing:
                    already_showing[img_id] = True
                    title = img_info.findtext('title', 'no title')
                    desc = img_info.findtext('description', 'no description')
                    location = img_info.find('location')
                    latlon = (location.get('latitude'), location.get('longitude')) if location is not None else None
                    dates = img_info.find('dates')
                    taken = dates.get('taken')
                    # issue with timezone here - tz is not it the flickr provided data
                    # (will use the posted time if we don't have a time taken)
                    when = datetime.datetime.strptime(taken, "%Y-%m-%d %H:%M:%S") if taken else FLICKR_TIME_ZERO + datetime.timedelta(int(dates.get('posted')))
                    #print(dirpath, dirnames, filename)
                    img_list.append((img_id, title, desc, dirpath, os.path.split(dirpath)[1], latlon, when))                
    return img_list


if __name__ == '__main__':
    opt_parser = OptionParser(
            usage='Usage: %prog [options] templateFolder imageFolder ', 
            description="Use templateFolder to create a slide-show inside imageFolder by creating an HTML sub-folder in imageFolder.")
    opt_parser.add_option('-r',  '--replace',  dest='replace', action='store_true', default=False,  help="Replace existing slide-show sub-folder in mirrorFolder")
    opt_parser.add_option('-n',  '--slide-show-name',  dest='showname', default="HTML-Slide-Show",  help="Name for the slide show folder within the mirrorFolder.")
    options, args = opt_parser.parse_args()

    if len(args) == 2:
        templatepath = args[0]
        mirrorpath = args[1]           
    else:
        opt_parser.print_help()
        sys.exit(1)

    # Find all image data in the mirrorpath
    img_list = read_image_data(mirrorpath)
    # Sort into date taken order                
    img_list.sort(key=itemgetter(6), reverse=True)
    
    template = ESTemplate(templatepath, mirrorpath, slide_show_name=options.showname, replace=options.replace)
    
    for (img_id, title, desc, dir_path, setname, latlon, when) in img_list:
        # Can only handle images (exclude videos)
        for ok_type in (".jpg", ".png", ".gif"):
            img_path = os.path.join(dir_path, img_id + ok_type)
            if os.path.exists(img_path):
                template.add(img_id, img_path, escape(title.strip()), create_html_description(desc))
                break
    
    template.finish()
    print("Done")
    
    
    
               
