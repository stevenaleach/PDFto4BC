#!/usr/bin/env python3

#import matplotlib.pyplot as plt
import numpy as np, os, sys, fitz, varint, tqdm
from operator import itemgetter
from itertools import groupby
from PIL import Image
from PIL.ImageOps import grayscale
bar = tqdm.tqdm

WIDTH  = 1404 # Default target screen size if no other values are
HEIGHT = 1872 # specified.
PLUS   = 8    # Default margin after trim.

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
    os.remove('temp.ppm')
    down = width / img.width
    rw = int(down*img.width); rh = int(down*img.height)
    img_resized = img.resize((rw,rh))
    if img_resized.height > height:
        down = height / img.height
        rw = int(down*img.width);rh = int(down*img.height)
        img_resized = img.resize((rw,rh))
    return(img_resized)

#//------- Returns stripped and cleaned page text -- which likely will not work
#//------- with multi-column .PDFs.
def get_text(page):
    def recover(words, rect):
        mywords = [w for w in words if fitz.Rect(w[:4]) in rect]
        mywords.sort(key=itemgetter(3, 0))  
        grouped_lines = groupby(mywords, key=itemgetter(3))
        words_out = [] 
        for _, words_in_line in grouped_lines:
            for i, w in enumerate(words_in_line):
                if i == 0: 
                    x0, y0, x1, y1, word = w[:5]
                    continue
                r = fitz.Rect(w[:4])  # word rect
                threshold = r.width / len(w[4]) / 5
                if r.x0 <= x1 + threshold:  
                    word += w[4]; x1 = r.x1; y0 = max(y0, r.y0)  
                    continue
                words_out.append([x0, y0, x1, y1, word])
                x0, y0, x1, y1, word = w[:5]
            words_out.append([x0, y0, x1, y1, word])
        return words_out
    oldwords = page.getTextWords(); newwords = recover(oldwords, page.rect)
    s = "" ; height = 0; line = ""
    for w in newwords:
        r = fitz.Rect(w[:4]); word = w[4] 
        if r.y1 != height: 
            s+=(line + "\n"); line = ""; height = r.y1 
        line += word + " " 
    s+=(line) 
    return((s.strip('\n')+'\n').replace('\t',' '))


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
#// return a new array, varint prefix is repition count
#// for the following byte, if the count prefix is zero, another varint 
#// specifies a byte-length of 'raw' bytes to follow.
def compress(inbar,page=False):
    i=0; outbar = []
    REP=(inbar[0]==inbar[1]); 
    UNQ = (inbar[0]==inbar[1])==False
    BLOCK = [];
    while i < len(inbar) - 2:
        BLOCK.append(inbar[i])
        state = UNQ; #save prior state
        i+=1; 
        REP=(inbar[i]==inbar[i+1]); 
        UNQ = (inbar[i]==inbar[i+1])==False
        if state != UNQ:
            if state == False: # was REP.
                if not len(outbar) or len(BLOCK) > 3 or len(outbar[-1]) == 2:
                    outbar.append([len(BLOCK),BLOCK[0]])
                    BLOCK = []
                else:
                    for b in BLOCK:
                        outbar[-1][-1].append(b);outbar[-1][1]+=1
                    BLOCK=[]
            if state == True: # was UNQ.
                outbar.append([0,len(BLOCK),bytearray()])
                for b in BLOCK:
                    outbar[-1][2].append(b)
                BLOCK = []
    if len(BLOCK):
        if state == False:
            outbar.append([len(BLOCK),BLOCK[0]])
        if state == True:
            outbar.append([0,len(BLOCK),bytearray()])
            for b in BLOCK:
                outbar[-1][2].append(b)
    while i < len(inbar):
        outbar.append([1,inbar[i]]); i+=1
    #Merge adjacent raw blocks.
    OUTBAR = []
    for block in outbar:
        if not len(OUTBAR):
            OUTBAR.append(block)
        else:
            if len(block) == 3 and len(OUTBAR[-1]) == 3:
                for b in block[-1]:
                    OUTBAR[-1][-1].append(b); OUTBAR[-1][1]+=1;
            else:
                OUTBAR.append(block)
    outbar = bytearray()
    for block in OUTBAR:
        if len(block) == 2:
            I = varint.encode(block[0])
            for i in I:
                outbar.append(i)
            outbar.append(block[1])
        if len(block) == 3:
            outbar.append(0)
            I = varint.encode(block[1])
            for i in I:
                outbar.append(i)
            for b in block[2]:
                outbar.append(b)            
    return(outbar)

#// --------- Takes a compressed byte-array, returns decompressed.
def decompress(inbar):
    i=0; outbar=bytearray();
    while i < len(inbar):
        repcount = varint.decode_bytes(inbar[i:])
        while inbar[i] >= 128:
            i+=1
        i+=1
        if repcount:
            while repcount:
                outbar.append(inbar[i]); repcount-=1;
            i+=1
        else:
            repcount = varint.decode_bytes(inbar[i:])
            while inbar[i] >= 128:
                i+=1
            i+=1
            while repcount:
                outbar.append(inbar[i]); i+=1; repcount-=1
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
#//      if a text string is passed, it will be appended.
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

#//---------- Get white-space bounds for a page (PIL Image)

def get_bounds(img):
    top=bottom=left=right=1
    arr = np.array(img)
    while left < arr.shape[1]//2 and arr[:,0:left].min() == 255:
        left+=1
    while right < arr.shape[1]//2 and arr[:,-right:].min() == 255:
        right+=1
    while top < arr.shape[0]//2 and arr[0:top,:].min() == 255:
        top+=1
    while bottom < arr.shape[0]//2 and arr[-bottom:,:].min() == 255:
        bottom+=1
    return(left,right,top,bottom)

#//-------- Scans (start to stop) a document, finds minimum trim
#// bounds (minus an optional pixel border, 'plus') for all pages
#// within the range specified, returns trim values:
#//  left, right, top, bottom.
def doc_bounds(doc,start=0,stop=False,plus=PLUS):
    if not stop:
        stop=len(doc)
    bounds = list(get_bounds(convert_page(doc[start])))
    for i in bar(range(start,stop)):
        BOUNDS = get_bounds(convert_page(doc[i]))
        for j in range(len(bounds)):
            bounds[j] = min(BOUNDS[j],bounds[j])
    return([(bound-plus)*2 for bound in bounds])


def main():
    width=WIDTH; height=HEIGHT; top=bottom=left=right=0;exclude=[];no_crop=[]
    start=0; stop=False; plus=PLUS;
    args = sys.argv[1:]
    cl_opts = {}; in_file = out_file = False
    text = True
    commands = ['display', 'convert','scan']
    options = ['width','height',
            'top','bottom','left','right',
            'exclude','no_crop',
            'start','stop','plus','text']
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
        if opt in ['height','width', 'top','bottom','left','right','start','stop','plus','text']:
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
    if 'start' in cl_opts:
        start = cl_opts['start']
    if 'stop' in cl_opts:
        stop = cl_opts['stop']
    if 'plus' in cl_opts:
        plus = cl_opts['plus']
    if 'text' in cl_opts:
        text = cl_opts['text']

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
        fields = ['title', 'title_sort','author', 'author_sort',  'year', 'month', 'day', 'tags']
        numeric = ['year','month','day']
        lower  = ['title_sort','author_sort']
        card = {}
        for field in fields:
            print()
            card[field] = input(field+': ')
            if field in numeric:
                while not (card[field].isnumeric() or card[field]==""):
                    print("Numeric value only for",field)
                    card[field] = input(field)
            if field == 'tags':
                s = ""; tags = card[field].split()
                while len(tags) > 1:
                    s+=tags.pop(0)+" "
                s+=tags.pop(0)
                card[field] = s
        f = open(out_file,'ab')
        for field in fields:
            if field in lower:
                card[field]=card[field].lower()
            f.write((field+'\t'+card[field]+'\n').encode())
        if text:
            doc = fitz.open(in_file); j=0;
            for i in range(len(doc)):
                if not i in exclude:
                    f.write(  (chr(1)+str(j)+chr(2)+get_text(doc[i])+chr(3)).encode()  ); j+=1
    if command == 'scan':
        print(cl_opts)
        in_file = fitz.open(in_file)
        left,right,top,bottom = doc_bounds(in_file,start=start,stop=stop,plus=plus)
        print('left:',left,
              'right:',right,
              ' top:',top,
              ' bottom:',bottom)

if __name__ == "__main__":
    main()

