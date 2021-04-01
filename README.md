# PDFto4BC

A small command line tool and Python library for scaling, cropping, and converting .PDF documents to format easily handled by low-power low-memory devices (microcontrollers).

### Usage:

There are three commands: scan, convert, and display - one of which must be the first argument on the command line.

If you want margins to be trimmed, you'll want to begin by 'scanning' the document to get cropping values. Scan accepts the options start and stop to specify a range of pages to be scanned (you will want it to ignore full page cover art, for instance). Example:

              $./PDFto4BC.py scan start 1 stop 53 The_Little_Prince.pdf 
              {'start': 1, 'stop': 53}
              Input File: The_Little_Prince.pdf
              Output File False
              0 arguments remaining and ignored.
              {'start': 1, 'stop': 53}
              100%|███████████████████████████████████████████████████████████████████| 52/52 [00:16<00:00,  3.15it/s]
              left: 144 right: 144  top: 140  bottom: 144

This returns cropping values to be used for conversion with a default eight-pixel margin (this may be overriden with other values by providing a 'plus' value on the command line - the default is equivalent to "plus 8".

Now you'll want to do the actual conversion:

              $ ./PDFto4BC.py convert left 144 right 144 top 140 bottom 144 The_Little_Prince.pdf The_Little_Prince.4bc
              {'left': 144, 'right': 144, 'top': 140, 'bottom': 144}
              Input File: The_Little_Prince.pdf
              Output File The_Little_Prince.4bc
              0 arguments remaining and ignored.
              100%|███████████████████████████████████████████████████████████████████| 54/54 [02:00<00:00,  2.23s/it]

              title: The Little Prince

              title_sort: little prince the

              author: Antoine de Saint-Exupéry

              author_sort: de Saint-Exupéry

              year: 1943

              month: 4

              day: 1

              tags: fable classic children's

              $ ls -lh *.4bc
              -rw-rw-r-- 1 stevenaleach stevenaleach 13M Mar 31 23:25 The_Little_Prince.4bc
             
 
### Options:
* scan: start stop plus height width
* convert: no_crop exclude left right top bottom text height width

An additional command, display, is provided to see how a page will look with given cropping options - useful along with scan to find optimal values and which pages not to scale and to exclude from the scan.

Height and width may be specified on the command line, if not provided the hard-coded default values will be used (HEIGHT, WIDTH) which you will want to change to match the resolution of your target screen.

