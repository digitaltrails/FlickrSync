#!/usr/bin/env python
"""
FlickrSync - a python script to download all your photos from flickr
along with descriptions and comments in xml.  Saves the download 
into a folder organised into sub-folders by set.

Once downloaded, the --recent-updates option can be used to get the
download up to date.

Uses the flickr REST API - basically we make signed requests via an
api and receive XML in a response.  The interaction is stateless, each
request is independent. 

Limitations: 
    Doesn't track/update when images are removed from sets/flickr.
    When run for the first time, the script needs to be able to start 
    a browser for the first handshake with flickr.
    
Home: codeincluded.blogspot.com

Version:       1.0

Author:          Michael Hamilton
   FlickrSync is an extensively modified and refactored fork of flickrtouchr:
   https://github.com/dan/hivelogic-flickrtouchr
   Flickrtouchr Author:       colm - AT - allcosts.net  - Colm MacCarthaigh - 2008-01-21
   Flickrtouchr Modified by:  Dan Benjamin - http://hivelogic.com	
                 Michael Hamilton - michael - AT - actrix.gen.nz    									

License:         Apache 2.0 - http://www.apache.org/licenses/LICENSE-2.0.html
                 Copyright (C) 2011 Michael Hamilton
"""
import xml.dom.minidom
import webbrowser
import urlparse
import urllib2
import unicodedata
import cPickle
import md5
import sys
import os
import shutil
import errno
import re
import datetime
import time
from xml.dom.minidom import getDOMImplementation
from optparse import OptionParser

API_KEY = "3ea1541ecb74098fcac6a457f4377ba6"
SHARED_SECRET = "39cb33fea46cb3e1"
FROB_CACHE = "flickrsync.frob.cache"

# Get 500 results per page - for downloading
PER_PAGE = 500

# Use photo ID as kind of inode - so we can store the image once
# and use file system links to refer to one image for all the sets
# the image resides in.
info_saved = {}
cache_index = {}

def gettext(dom, tagname):
    """
    Helper function to extract text from a dom node
    """
    nodelist = dom.getElementsByTagName(tagname)[0].childNodes
    rc = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc = rc + node.data
    return rc.encode("utf-8")

def do_request(url, debug=False):
    """
    Make a REST request to flickr, check the rst error status.
    
    Return: the XML parsed into a DOM
    """
    if debug: print "request: ", url
    # Make the request
    response = urllib2.urlopen(url)
    # Parse the reponse XML
    dom = xml.dom.minidom.parse(response)
    if debug: print "response:", dom.toxml(encoding="UTF-8")
    if dom.getElementsByTagName("rsp")[0].getAttribute("stat") != "ok":
        print "Flickr request failed:", dom.toxml(encoding="UTF-8")
        raise Exception("flickr request failed")
    return dom

def do_frob_request():
    """
    Request a frob based on our API_KEY and shared secret.
    Utility functions for dealing with flickr authentication.
    
    Return: frob
    """
    # Create our signing string
    string = SHARED_SECRET + "api_key" + API_KEY + "methodflickr.auth.getFrob"
    sig_hash   = md5.new(string).digest().encode("hex")

    # Formulate the request
    url    = "http://api.flickr.com/services/rest/?method=flickr.auth.getFrob"
    url   += "&api_key=" + API_KEY + "&api_sig=" + sig_hash

    try:
        # Make the request and extract the frob
        dom = do_request(url)
        frob = gettext(dom, "frob")
        dom.unlink()
        return frob
    except Exception:
        print "Could not retrieve frob"
        raise


def do_frob_login(frob, perms):
    """
    Login and get a token - uses deprecated API, should switch to new one?
    On first run it will invoke the browser to do a user-flicker-app handshake.
    """
    string = SHARED_SECRET + "api_key" + API_KEY + "frob" + frob + "perms" + perms
    sig_hash   = md5.new(string).digest().encode("hex")

    # Formulate the request
    url    = "http://api.flickr.com/services/auth/?"
    url   += "api_key=" + API_KEY + "&perms=" + perms
    url   += "&frob=" + frob + "&api_sig=" + sig_hash

    # Tell the user what's happening
    print "In order to allow FlickrTouchr to read your photos and favourites"
    print "you need to allow the application. Please press return when you've"
    print "granted access at the following url (which should have opened"
    print "automatically)."
    print
    print url
    print 
    print "Waiting for you to press return"

    # We now have a login url, open it in a web-browser
    webbrowser.open_new(url)

    # Wait for input
    sys.stdin.readline()

    # Now, try and retrieve a token
    string = SHARED_SECRET + "api_key" + API_KEY + "frob" + frob + "methodflickr.auth.getToken"
    hash   = md5.new(string).digest().encode("hex")
    
    # Formulate the request
    url    = "http://api.flickr.com/services/rest/?method=flickr.auth.getToken"
    url   += "&api_key=" + API_KEY + "&frob=" + frob
    url   += "&api_sig=" + hash

    # See if we get a token
    try:
        # Make the request and extract the frob
        dom = do_request(url)
        # get the token and user-id
        token = gettext(dom, "token")
        nsid  = dom.getElementsByTagName("user")[0].getAttribute("nsid")
        dom.unlink()
        return (nsid, token)
    except Exception as error:
        print "Login failed", 
        raise error

def get_flickr_authorization():
    """
    Load a cached authorisation token or request a new one from flickr (and cache it).
    """
    try:
        # First things first, see if we have a cached user and auth-token
        cache_file = open(FROB_CACHE, "r")
        auth = cPickle.load(cache_file)
        cache_file.close()
    except:
        # We don't - get a new one
        (user, token) = do_frob_login(do_frob_request(), "read")
        auth = { "version":1 , "user":user, "token":token }  
        # Save it for future use
        cache_file = open(FROB_CACHE, "w")
        cPickle.dump(auth, cache_file)
        cache_file.close()
    return auth

def sign_flickr_url(url, token):
    """
    Sign an arbitrary flickr request with a token.
    
    Return: the signed requesy url
    """
    query  = urlparse.urlparse(url).query
    query += "&api_key=" + API_KEY + "&auth_token=" + token
    params = query.split('&') 

    # Create the string to hash
    string = SHARED_SECRET
    
    # Sort the arguments alphabetically
    params.sort()
    for param in params:
        string += param.replace('=', '')
    sig_hash   = md5.new(string).digest().encode("hex")

    # Now, append the api_key, and the api_sig args
    url += "&api_key=" + API_KEY + "&auth_token=" + token + "&api_sig=" + sig_hash
    
    # Return the signed url
    return url
    
def do_signed_request(auth, method, args={}, debug=False):
    """
    Performs a flickr api request URL from method name and args, the request
    is signed using the auth token.
    
    Return: dom from the response
    """
    # Construct full URL from method name and args
    url  = "http://api.flickr.com/services/rest/?method=" + method
    for arg, value in args.items():
        url += "&" + arg + "=" + value
        
    url  = sign_flickr_url(url, auth["token"])
    return do_request(url, debug)

    
def save_xml(dom, tagname, filename):    
    """
    Extract a node called tagname from a rsp dom object and save it to filename.
    """
    nodelist = dom.getElementsByTagName(tagname)
    if nodelist == None or nodelist.length == 0:
        print "Failed to retrieve info:", tagname, filename
        return
    node = nodelist.item(0).cloneNode(True)

    impl = getDOMImplementation()
    newdoc = impl.createDocument(None, None, None)
    newdoc.appendChild(node)
    fh = open(filename, "w")
    #fh.write(dom.toxml("utf-8"))
    fh.write(newdoc.toprettyxml(indent="  ", encoding="utf-8"))
    fh.close()   
    newdoc.unlink()

def link_local_file(fromfile, tofile, use_copy=False):
    """
    Hard links fromfile to tofile. On Windows a copy is used instead of a link.
    If options.do_links is False, then copies instead of linking.
    """
    if os.name == 'posix' and not use_copy:
        if os.path.exists(tofile):
            if os.path.samefile(fromfile, tofile):
                return # already linked
            try:        
                os.remove(tofile) # force the link by getting rid of the file
            except OSError as error:
                if error.errno !=  errno.ENOENT:
                    raise
        print "    Link file     :", fromfile, "-->", tofile
        os.link(fromfile, tofile)
    else:  # boo, os lacks links
        print "    Copy file     :", fromfile, "-->", tofile
        if os.path.exists(tofile):
            try:        
                os.remove(tofile)
            except OSError as error:
                if error.errno !=  errno.ENOENT:
                    raise
        shutil.copyfile(fromfile, tofile)        

def download_size_info(auth, photoid):
    """
    Download the image size options from the server
    
    Return the filename the image was saved to
    """
    imgurl = None
    media = None
    try:
        # Perform a request to find the sizes
        dom = do_signed_request(auth, "flickr.photos.getSizes", {"photo_id":photoid})
        #print dom.toxml(encoding="UTF-8")
        # Get the list of sizes
        sizes =  dom.getElementsByTagName("size")
        # Grab the original if it exists
        biggest = sizes[-1]
        imgurl = biggest.getAttribute("source")
        media = biggest.getAttribute("media")
        label = biggest.getAttribute("label")
        if label.count("Original") == 0:
            print "Failed to get original for", media, "id ", photoid
    except Exception as error:
        print "Failed to retrieve photo sizes", photoid, error
    return (imgurl, media)

def download_media(auth, imgurl, proto_name):
    """
    Download the actual the photo from the server.
    Proto_name is the path and name lacking a file type suffix.
    The suffix will be determined from the download response and the
    final path/name.suffix will be returned.
    
    Return the filename the image was saved to
    """
    try:
        response = urllib2.urlopen(imgurl)
        # Work out file type from response
        file_type = ""  
        if response.info().has_key('Content-Type'):
            content_type = response.info()['Content-Type'].split('image/')[1]
            file_type = "." + (content_type if content_type != "jpeg" else "jpg")
        if response.info().has_key('Content-Disposition'):                
            content_name = response.info()['Content-Disposition'].split('filename=')[1]
            file_type = os.path.splitext(content_name)[1]
        filename = proto_name + file_type
        data = response.read()    
        # Save the file!
        fh = open(filename, "w")
        fh.write(data)
        fh.close()
    except Exception as error:
        print "Failed to retrieve photo id", photoid, error
        filename = None
    return filename

def download_photo(auth, photo_dom, localdir, use_links=True, force_refresh=False):
    """
    Download the photo image and save it - won't download
    if we already have it (pass refresh=True to force a refresh).
    
    Links or copies files across sets if they are the same - so a
    file is only downloaded once.
    """
    global cache_index # photos saved this run
    photoid = photo_dom.getAttribute("id")

    # Have we seen this image already on this run?
    if photoid in cache_index and cache_index[photoid] and os.access(cache_index[photoid], os.R_OK):
        # Aready encountered on this run, use cache copy
        target = os.path.join(local_dir, os.path.basename(cache_index[photoid]))
        link_local_file(cache_index[photoid], target, use_copy=not use_links)
        return
        
    # OK, haven't seen it yet, has it been cached on disk by a previous run? 
    if not force_refresh:
        # Don't seem to be able to tell what kind of video something is until we
        # download it - so guess every possibility when looking in the cache
        possible_types = (".jpg", ".gif", ".png", ".video", ".mpg", ".avi", ".mov", ".mpeg", ".3gp", ".m2ts", ".ogg", ".ogv", "")   
        for filetype in possible_types:
            target = os.path.join(localdir, photoid + filetype)
            if os.path.exists(target):
                # First time encountered on this run, but already on disk
                cache_index[photoid] = target
                return
                
    # Need to download from scratch
    imgurl, media = download_size_info(auth, photoid)
    if imgurl:
        proto_name = os.path.join(local_dir, photoid)
        print "    Download", media, ":", local_dir, photo_dom.getAttribute("title").encode("utf8"), "[ id=" + photoid, "]"
        finalname = download_media(auth, imgurl, proto_name)
        if finalname:
            cache_index[photoid] = finalname

def download_photoinfo(auth, photo_dom, local_dir, use_links=True, refresh=False):
    """
    Download the XML info for a photo and save it - won't download
    if we already have it (pass refresh=True to force a refresh).
    
    Links or copies files across sets if they are the same - so a
    file is only downloaded once.
    """        
    global info_saved
    photoid = photo_dom.getAttribute("id")
    photoxml = os.path.join(local_dir, photoid + ".xml")    
    if photoid in info_saved and os.access(info_saved[photoid], os.R_OK):
        link_local_file(info_saved[photoid], photoxml, use_copy=not use_links)
    else:
        if os.path.exists(photoxml) and not refresh:
            info_saved[photoid] = photoxml
            return
    
        print "    Download info: ", local_dir, photo.getAttribute("title").encode("utf8")
        photo_dom = do_signed_request(auth, "flickr.photos.getInfo", { "photo_id":photoid })
        num_comments = int(str.strip(gettext(photo_dom, "comments")))
              
        save_xml(photo_dom, "photo", photoxml) 
        info_saved[photoid] = photoxml
        
        print "         Comments: ", num_comments
        comments_dom = do_signed_request(auth, "flickr.photos.comments.getList", { "photo_id":photoid })
        commentsfile = os.path.join(local_dir, photoid + "-comments.xml")
        save_xml(comments_dom, "comments", commentsfile)
        comments_dom.unlink()
                            
        # Free the DOM memory
        photo_dom.unlink()

def download_collections_info(auth, filename):
    """
    Download and save the flickr collections XML info
    """
    dom = do_signed_request(auth, "flickr.collections.getTree", {"user": auth["user"]})
    print "Download collections info:", filename
    save_xml(dom, "collections", filename)
    dom.unlink()        
    
def download_sets_info(auth, filename):
    """
    Download and save the flickr set XML info
    """
    print "Download photosets info:", filename
    photosets_dom = do_signed_request(auth, "flickr.photosets.getList", {"user": auth["user"]})   
    save_xml(photosets_dom, "photosets", filename)      
    return photosets_dom

def recently_updated(auth, days):
    """
    Download the list of recently updated photo ID's from flickr.
    If days is zero, then the date on the FROB_CACHE is used and updated.
    
    Return: a list of photo ID's
    """
    print "Download updates data for last ", days, "days"
    unix_time = time.mktime((datetime.datetime.now() - datetime.timedelta(days=days)).timetuple()) if days > 0 else os.path.getmtime(FROB_CACHE)
    photo_ids = []
    pages = page = 1
    while page <= pages:           
        updated_dom = do_signed_request(auth, "flickr.photos.recentlyUpdated", { "min_date":str(unix_time), "per_page":str(PER_PAGE), "page":str(page) })
        # Get the total pages in the results
        pages = int(updated_dom.getElementsByTagName("photos")[0].getAttribute("pages"))
        for photo in updated_dom.getElementsByTagName("photo"):
            photo_id = photo.getAttribute("id")
            photo_ids.append(photo_id)
        page = page + 1
    return photo_ids

def create_list_requests(sets_dom, specific_set_ids=None, do_favourites=False):
    """
    Create a list of flickr requests for the sets we need to examine.
    Which sets to examine depends on options, by default we create requests for
    all sets, for photos not in a set, and for the users favorites.
    
    There is an option that disables getting favorites.

    There is an option that can be used to target specific sets.
    
    Decide on a local destination directory for each set based on the set name.

    Return: a list of tuples, each tuple is (flickrMethodName, args, destLocalDir)    
    """
    # Get the list of Sets
    photo_sets =  sets_dom.getElementsByTagName("photoset")
    extras = "original_format,last_update,media,url_o"
    # For each set - create a url
    sets_to_get = []
    for photo_set in photo_sets:
        photoset_id = photo_set.getAttribute("id")
        if specific_set_ids == None or photoset_id in specific_set_ids:
            local_dir = gettext(photo_set, "title")
            local_dir = re.sub(':', '-', re.sub('[/\\\\]','--', unicodedata.normalize('NFKD', local_dir.decode("utf-8",
"ignore")).encode('ASCII', 'ignore'))) # Normalize to ASCII
            # Build the list of get set of photos
            sets_to_get.append( ("flickr.photosets.getPhotos", { "photoset_id":photoset_id, "extras":extras }, local_dir) )
    if specific_set_ids == None:
        # Add the photos which are not in any set
        sets_to_get.append( ("flickr.photos.getNotInSet", {}, "No Set") )
        if do_favourites:
            # Add the user's Favourites
            sets_to_get.append( ("flickr.favorites.getList", {}, "Favourites") )
    return sets_to_get

def create_local_path(local_dir):
    try:
        os.makedirs(local_dir)
        return True
    except OSError as oserror:
        if oserror.errno != errno.EEXIST:
            raise OSError
    return False

      
######## Main Application ##########
if __name__ == '__main__':

    optParser = OptionParser(
            usage='Usage: %prog [options] destinationFolder ', 
            description="Download your flickr images along with descriptions and comments in xml. Also includes your favourited images.")
    optParser.add_option('-s',  '--setids',  dest='setids', default=None,  help='Do specified numeric set IDs only.')
    optParser.add_option('-r',  '--recent-updates',  type="int", dest='recent_updates', default=-1,  help="Find updates newer than N days old. -1 for updates newer than the last run time")
    optParser.add_option('-f',  '--include-favourites',  dest='do_favourites', action='store_true', default=False,  help='Download favourites (in available size only).')
    optParser.add_option('-X',  '--exclude-metadata',  dest='do_metadata', action='store_false', default=True,  help="Do not download descriptions, etc as xml.")
    optParser.add_option('-L',  '--no-links',  dest='do_links', action='store_false', default=True,  help="Do not use file links, copy files instead.")
    (options, args) = optParser.parse_args()

    if len(args) == 1:
        # Change to the destination directory to make it easier to refer to filenames.
        os.chdir(args[0])
    else:
        optParser.print_help()
        sys.exit(1)

    # Get flickr authentication data - new or from FROB_CACHE
    auth = get_flickr_authorization()
    
    # Get the user's flickr sets
    photosets_dom = download_sets_info(auth, "photosets.xml")
    # Save the photosets meta data
    if options.do_metadata: download_collections_info(auth, "collections.xml")
        
    # For each set - create a flickr REST url to get its contents
    specific_set_ids = options.setids.split(",") if options.setids else None
    sets_to_get = create_list_requests(photosets_dom, specific_set_ids, options.do_favourites)
    photosets_dom.unlink()

    # If the user only wants recent stuff, ask flickr for recently updated photo ID's
    only_these_photo_ids = recently_updated(auth, options.recent_updates) if options.recent_updates != -1 else None
    if options.recent_updates != -1  and len(only_these_photo_ids) == 0:
        print "No updates"
        sys.exit(0)

    # Time to get the list of photos for each set, and download each photo
    for (op, args, local_dir) in sets_to_get:
        
        print "Examining set:", local_dir 
        if create_local_path(local_dir): print "  Created folder:", local_dir 

        # Get 500 results per page (there is a limit, we can't get them all at once)
        args["per_page"] = str(PER_PAGE)

        pages = page = 1
        while page <= pages:
            # Get the current page number
            args["page"] = str(page)
            # Get this page from the set
            photos_dom = do_signed_request(auth, op, args)             
            photo_elems = photos_dom.getElementsByTagName("photo")
            # Get the total pages in the results - parentNode type varies, so we climb up from photo
            if photo_elems.length != 0: pages = int(photo_elems[0].parentNode.getAttribute("pages"))                    
            # Grab the actual photos
            for photo in photo_elems:
                photoid = photo.getAttribute("id")
                force_download = only_these_photo_ids and photoid in only_these_photo_ids
                if options.do_metadata: download_photoinfo(auth, photo, local_dir, options.do_links, force_download)
                download_photo(auth, photo, local_dir, options.do_links, force_download)
            photos_dom.unlink()
            # Move on the next page
            page = page + 1
            
    if options.recent_updates == 0:
        # Use the date/time on the FROB_CACHE to save last update time
        os.utime(FROB_CACHE, None)
