# PDFto4BC

A small command line tool and Python library for scaling, cropping, and converting .PDF documents to a 16-shade (e-ink targeted) format easily handled by low-power low-memory devices (microcontrollers). The container format includes meta-text (title, author, etc.) as well as a plain-text "transcript" (line breaks preserved, but all extraneous whitespace and blank lines removed, single space separation between words) for each page in addition to high quality compressed lossless pixmaps at the desired target resolution. In lieu of a desktop viewer, see this notebook https://github.com/stevenaleach/PDFto4BC/blob/main/4BC.ipynb for an idea of how to inspect converted documents.

Page pixmaps are run-length compressed packed-nibble bytes with varint runlengths, and a zero-prefix followed by a varint runlength flagging raw byte blocks, while runlengths without a zero prefix specify repititions for the single byte which follows.

The container format is relatively simple:

    uint16, little endian: width
    uint16, little endian: height
    uint16, little endian: pages
    uint32, little endian: byte-count page 0
    uint32, little endian: byte-count page 1
    ..
    uint32, little endian: byte-count last page.
    uint32, little endian: 0 terminator for index.
    [n bytes compressed pixmap page 0]
    [n bytes compressed pixmap page 1]
    ...
    [n bytes compressed pixmap last page]
    [begin meta-text, if any]

Following the pixmaps, meta-text followed by document text may be (and by default is) included. This text block begins with tab separated key-value pair lines and, if page transcript text is include (which by default it is), each page transcript will be prefixed by ASCII control character 1 (Start of Heading), the 'printed' (ASCII decimal representation) page number, followed by control character 2 (start of text), the page text (utf-8 encoded), and control character 3 (end of text) at the end of each page -- ASCII decimal representation for page numbers (starting at 0) are used rather than integers and standard ASCII control characters for delimiters so that the text block can be easily dumped and viewed, or otherwise treated as plain-text.

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

