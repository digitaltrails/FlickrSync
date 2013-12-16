FlickrSync
==========

It seems there is already a program called FlickrSync in the M$ Windows
realm.  I guess I will need to come up with a new name at some point.

A python script to mirror flicker images and metadata.  A second script to 
create a standalone HTML slideshow from the mirror browseable via file:///

## FlickrSync - mirror a flickr user's images to a folder

FlickrSync - a python script to download all your photos from flickr
along with descriptions and comments in xml.  Saves the download
into a folder organised into sub-folders by set.

Once downloaded, the --recent-updates option can be used to get the
download up to date.

When run for the first time, the script needs to be able to start
a browser for the first handshake with flickr.

### Usage

    flickrsync.py [options] destinationFolder

### Options:
```
  -h, --help            show this help message and exit
  -s SETIDS, --setids=SETIDS
                        Do specified numeric set IDs only.
  -r RECENT_UPDATES, --recent-updates=RECENT_UPDATES
                        Find updates newer than N days old. -1 for updates
                        newer than the last run time
  -f, --include-favourites
                        Download favourites (in available size only).
  -X, --exclude-metadata
                        Do not download descriptions, etc as xml.
  -L, --no-links        Do not use file UNIX links, copy files instead.
                        (For images in more than one set.)
```                        
### Limitations:
Doesn't track/update when images are removed from sets/flickr.

## FlickrShow - create an HTML slideshow for a  mirror

Create a slideshow sub-folder inside a flickrsync.py mirror
folder.  Currently the slideshow is based on a modified version of the
Responisive Image Gallery:

http://tympanus.net/codrops/2011/09/20/responsive-image-gallery/

Dendencies on the slideshow are minimal, it would be easy to plug in
different Javascript slide show templates - they all seem to function in
a similar way.

### Usage

    flickrshow.py [options] templateFolder imageFolder

### Options
```
  -h, --help            show this help message and exit
  -r, --replace         Replace existing slide-show sub-folder in mirrorFolder
  -n SHOWNAME, --slide-show-name=SHOWNAME
                        Name for the slide show folder within the
                        mirrorFolder.
```

## Example

1. Create a folder to store the mirror:
    mkdir /home/michael/FlickrMirror

2. Download your flickr images:
```
   python flickrsync.py /home/michael/FlickrMirror/
```
   On the first run the script will open a browser window to
   obtain permission to download from flickr.
   Once you have granted permission, return to window running
   the script and press return to continue with the script.

   All your images and meta data will be downloaded to the specified folder.

3. Download the ResponsiveImageGallery zip from:
```
   http://tympanus.net/codrops/2011/09/20/responsive-image-gallery/
```

4. Setup a template ResponsiveImageGallery and copy in the template:
```
   unzip ResponsiveImageGallery.zip
   cp ResponsiveTemplate.html ResponsiveImageGallery/template.html
```

5. Run flickrshow:
```
   python flickrshow.py ResponsiveImageGallery/ /home/michael/FlickrMirror
```
6. Browse the slideshow URL:
```
   file:///home/michael/FlickrMirror/HTML-Slide-Show/index.html
```
