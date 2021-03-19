#!/usr/bin/env python3

#import matplotlib.pyplot as plt
import numpy as np, os, sys, fitz
from PIL import Image
from PIL.ImageOps import grayscale

WIDTH  = 1404 # Default target screen size if no other values are
HEIGHT = 1872 # specified.

#// ----------- Takes PyMuPDF page scaled, but not stretched
#// to return a PIL Image to fit the target display, or optionally
#// the target area doubled in both dimensions for downscaling.
def convert_page(page, width=WIDTH, height=HEIGHT, double=False):
    if double:
        width*=2;height*=2
    amp = True; scale = 1.0
    while amp:
        matrix = fitz.Matrix(scale,scale)
        pix_width,pix_height=list([(p.w,p.h)for p in\
                                   [page.get_pixmap(alpa=False,
                                                    matrix=matrix)]][0])
        if pix_width > width:
            amp=False
        else:
            scale+=1
    page.get_pixmap(alpa=False,matrix=matrix).writePNG('temp.ppm')
    img = grayscale(Image.open('temp.ppm'))
    down = width / img.width
    rw = int(down*img.width); rh = int(down*img.height)
    img_resized = img.resize((rw,rh))
    if img_resized.height > height:
        down = height / img.height
        rw = int(down*img.width);rh = int(down*img.height)
        img_resized = img.resize((rw,rh))
    return(img_resized)

#// ---------- Takes PyMuPDF page, coverts to over-scale PIL Image
#// and then downscales with optional edge trims, stretching to fit
#// the target display.
def trim_scale_page(page,left=0,right=0,top=0,bottom=0,
                    width=WIDTH,height=HEIGHT):
    img = convert_page(page,width=width,height=height,double=True)
    img = img.crop((left, top, img.width-right, img.height-bottom))
    return(img.resize((width,height)))

#// ------- Takes PIL Image and returns a byte array of pixels,
#// one byte per pixel with 16 values 0 to 255 (n*17, 0 to 15)
def img_bytes(img):
    shift = [0, 17, 34, 51, 68, 85, 102, 119, 136, 153, 170, 187, 
             204, 221, 238, 255]
    a = (np.array(img).reshape(-1).astype(np.float32)/255*(15)).astype(np.uint8)
    for i in range(len(a)):
        a[i] = shift[a[i]]
    return(bytearray(a))
#// ------ Takes PyMuPDF page, trims and scales, returns 16 shade
#// byte array.
def convert(page,left=0,right=0,top=0,bottom=0,
                    width=WIDTH,height=HEIGHT):
    img = trim_scale_page(page=page,left=left,right=right,top=top,
                         bottom=bottom, width=width,height=height)
    bar = img_bytes(img)
    return(bar)

#// ------ For use in Jupyter Notebooks... 
# def show(bar,height=HEIGHT,width=WIDTH):
#     a = np.frombuffer(bar, dtype=np.uint8)
#     if len(set(a)) == 1 and a[0] == 255:
#         a[0]=244 #fix for pyplot.imshow that shows black for blank pages.
#     a = a.reshape(height,width)
#     plt.figure(figsize=(8.5*2,11*2))
#     plt.imshow(a,cmap='Greys_r')
#     plt.show()

#// ------ Packs byte array into nibbles, discarding the bottom bits.
def pack_nibbles(bar):
    barnew = bytearray(); i = 0
    while i < len(bar):
        barnew.append(int( (bar[i]//16)*16 + bar[i+1]//16 ))
        i+=2
    return(barnew)

#// ------ Unpacks nibble pairs to bytes, adjust such that 0xF->255,
#// 0->0 (n*17)
def unpack_nibbles(bar):
    shift = [0, 17, 34, 51, 68, 85, 102, 119, 136, 153, 170, 187, 
             204, 221, 238, 255] # Lookup table to speed things up.
    barnew = bytearray();
    for b in bar:
        barnew.append(shift[b//16])
        barnew.append(shift[b&0x0f])
    return(barnew)
#// -------- Takes byte array and performs run-length encoding to
#// return a new array, one-byte prefix 1 to 255 is repition count
#// for the following byte, if the count prefix is zero, the next
#// byte specifies a byte-length, 1 - 255, of 'raw' bytes to follow.
def compress(inbar):
    i=0; outbar = bytearray()
    REP=(inbar[0]==inbar[1]); 
    UNQ = (inbar[0]==inbar[1])==False
    BLOCK = [];
    while i < len(inbar) - 2:
        BLOCK.append(inbar[i])
        state = UNQ; #save prior state
        i+=1; 
        REP=(inbar[i]==inbar[i+1]); 
        UNQ = (inbar[i]==inbar[i+1])==False
        if state != UNQ or len(BLOCK) == 255: 
            if state == False: # was REP.
                outbar.append(len(BLOCK))
                outbar.append(BLOCK[0])
                BLOCK = []
            if state == True: # was UNQ.
                outbar.append(0)
                outbar.append(len(BLOCK))
                for b in BLOCK:
                    outbar.append(b)
                BLOCK = []
    if len(BLOCK):
        if state == False:
            outbar.append(len(BLOCK))
            outbar.append(BLOCK[0])
        if state == True:
            outbar.append(0)
            outbar.append(len(BLOCK))
            for b in BLOCK:
                outbar.append(b)
    while i < len(inbar):
        outbar.append(1); outbar.append(inbar[i]); i+=1
    return(outbar)

#// --------- Takes a compressed byte-array, returns decompressed.
def decompress(bar):
    i=0; outbar = bytearray()
    while i < len(bar) - 1:
        c = bar[i]; i+=1
        if c > 0:
            for j in range(c):
                outbar.append(bar[i])
            i+=1
        if c == 0:
            c = bar[i]; i+=1
            for j in range(c):
                outbar.append(bar[i]); i+=1
    return(outbar)

#// ------------ Returns a list containing compressed pages as byte
#// arrays, with optional trim values and list of pages to be left
#// untrimmed.
def compress_pages(file,top=0,bottom=0,left=0, width=WIDTH, 
                   height=HEIGHT,right=0,no_crop=[],stop=False,
                   exclude=[]):
    import tqdm
    bar = tqdm.tqdm
    pages = []
    doc = fitz.open(file)
    for i in bar(range(len(doc))):
        if stop:
            if i > stop:
                break
        crop = 1
        if i in no_crop:
            crop = 0
        if not i in exclude:
            pages.append(compress(pack_nibbles(convert(doc[i],
                                        height=height,
                                        width=width,
                                        top=top*crop,
                                        bottom=bottom*crop,
                                        left=left*crop,
                                        right=right*crop))))  
    return(pages)
#// -------- Takes list of pages and saves to a single file 
#//      with header information:
#//          uint16 width, uint16 height, uint16 page count,
#//      followed bin index:
#//          uint32 null-terminated list of byte-sizes for pages
#//      followed by a non-terminated concatenation of pages.
#//
def save_document(pages, filename, text='',
                  width=WIDTH, height=HEIGHT):
    bar = bytearray()
    for b in int.to_bytes(width,2,'little'):
        bar.append(b)
    for b in int.to_bytes(height,2,'little'):
        bar.append(b)
    for b in int.to_bytes(len(pages),2,'little'):
        bar.append(b)
    for page in pages:
        for b in int.to_bytes(len(page),4,'little'):
            bar.append(b)
    for i in range(4):
        bar.append(0) # A null terminator for the index.
    for page in pages:
        for b in page:
            bar.append(b)
    file = open(filename,'wb')
    file.write(bar)
    file.write(text.encode())
    file.close()
#// -------------- Load file and return width, height, and list
#// containing compressed pages.
def load_document(filename):
    bytecounts = []
    buff = []
    file   = open(filename,'rb')
    width  = int.from_bytes(file.read(2),'little')
    height = int.from_bytes(file.read(2),'little')
    pages  = int.from_bytes(file.read(2),'little')
    #print(width, height, pages)
    count = int.from_bytes(file.read(4),'little')
    while count:
        bytecounts.append(count)
        count = int.from_bytes(file.read(4),'little')
    for count in bytecounts:
        buff.append(file.read(count))
    text = file.read().decode()
    return((width, height, text), buff)

def main():
    width=WIDTH; height=HEIGHT; top=bottom=left=right=0;exclude=[];no_crop=[]
    args = sys.argv[1:]
    cl_opts = {}; in_file = out_file = False
    commands = ['display', 'convert']
    options = ['width','height','top','bottom','left','right','exclude','no_crop']
    if not len(args) or not args[0].lower() in commands:
        print('Valid command options are:',commands)
        _=1/0
    command = args.pop(0)
    if command == 'display':
        if not len(args) or not args[0].isnumeric():
            print('Invalid page number for display')
            _=1/0
        else:
            page_number = [int(args.pop(0))]
        while len(args) and args[0].isnumeric():
            page_number.append(int(args.pop(0)))
    while len(args) and args[0].strip('-') in options:
        opt = args.pop(0); l = []
        while len(args) and args[0].isnumeric():
            l.append(int(args.pop(0)))
        cl_opts[opt]=l
        if opt in ['height','width', 'top','bottom','left','right']:
            cl_opts[opt]=cl_opts[opt][0]

    if not len(args):
        print('No input file specified.')
        _=1/0
    else:
        if os.path.exists(args[0]):
            in_file = args.pop(0)
        else:
            print('Input file',args[0], 'not found.')
            _=1/0
    if command == 'convert':
        if not len(args):
            print('No output file specified')
            _=1/0   
        else:
            out_file = args.pop(0)
    print(cl_opts)
    print('Input File:',in_file)
    print('Output File', out_file)
    print(len(args),'arguments remaining and ignored.')
    if 'height' in cl_opts:
        height=cl_opts['height']
    if 'width' in cl_opts:
        width=cl_opts['width']
    if 'top' in cl_opts:
        top=cl_opts['top']
    if 'bottom' in cl_opts:
        bottom=cl_opts['bottom']
    if 'left' in cl_opts:
        left=cl_opts['left']
    if 'right' in cl_opts:
        right=cl_opts['right']
    if 'exclude' in cl_opts:
        exclude=cl_opts['exclude']
    if 'no_crop' in cl_opts:
        no_crop = cl_opts['no_crop']

    if command == 'display':
        doc = fitz.open(in_file)
        for n in page_number:
            print('Page',n)
            page = list(doc)[n]
            img = trim_scale_page(page, height=height,width=width,top=top,bottom=bottom,
                    left=left,right=right)
            img.show()

    if command == 'convert':
        pages = compress_pages(in_file, no_crop=no_crop, exclude=exclude,
                top=top,bottom=bottom,left=left,right=right,width=width,height=height)
        save_document(pages,out_file,width=width,height=height)

if __name__ == "__main__":
    main()

