# PDFto4BC

# OUTDATED: I'm going to be re-implementing the compression/decompression - we  can do better ;-) Variable-length unsigned ints for run-lengths instead of batches of 255 max, and two-bit additive/subtractive values with a base value and sign for prefix should pack much of the raw byte blocks at four pixels per block... compression should be a lot better and still easy for the microcontroller to handle... 

A tool to convert .PDF documents to a paginated four-bit depth packed-pixel run-length encoded format with appended text metadata. Allows for optional cropping and scales to a specified target display's dimensions. The "4bc" format is intended to be easily parsed and decompressed a page at a time by low-power small memory devices (microcontrollers) while still providing reasonably good compression. 

Originally created for a personal DIY e-reader project based on an ESP32 and WaveShare e-ink display (1404x1872, four-bit per pixel), which is why these are the default height and width in the code if no other values are specified.

### Usage:
      ./PDFto4BC [display/convert] [pages to display] [options] input_file [output_file]
  

#### display:
display, followed by one or more page numbers will display a preview of the cropped/stretched/16-shade converted pages specified.
This is to be able to find the 'ideal' edge cropping (and which pages to exclude from said cropping) for the document by trial and error from the command line.

Example:

      ./PDFto4BC display 1 2 3 98 99 100 height 1024 width 768 top 25 bottom 30 left 10 right 20 input.pdf
      
will display the six listed pages with the 'zoom' that will result from the specified edge trims.

#### convert:
convert accepts optional arguments no_crop and exclude, those pages in the no_crop list will not be trimmed before downscaling to the target width and height, those pages in the exclude list will be left out entirely.

Example:

      ./PDFto4BC convert width 500 height 1000 top 10 bottom 10 left 25 right 15 no_crop 0 3 199 exclude 2 197 198 input.pdf output.4bc

will convert and include all pages not listed in 'exclude', trim/zoom with the specified edge cropping all pages not listed in 'no_crop', and will store the output in a new file named 'output.4bc'
      
#### Adding Metadata:
You'll notice no options to include metadata, and that's because it consists of free-form text that may optionally be appended to the file (using `cat >> output.4bf`, for instance). The file is perfectly valid without it, and any text appended is fine (I've been using it to add tab separated key-value strings, one per line, with author, title, and year on the files I've been playing with so far).

#### Inspecting/Viewing the resuting file in a Jupyter Notebook:

No tool is provided above to easily inspect/view the output document... the easiest and most convenient way is in a Jupyter Notebook.  The following code pasted in to a notebook should load the example file, print out it's height, width, number of pages, the text meta-data, and will then display the first ten pages in the notebook:

          import numpy as np, os, sys, matplotlib.pyplot as plt
          from PIL import Image
          import PDFto4BC as B4

          _,pages = B4.load_document('./The_Little_Prince_500x1000.4bc')
          WIDTH,HEIGHT,TEXT =_

          print('Width',WIDTH)
          print('Height',HEIGHT)
          print(len(pages),'pages')
          print('Meta-Text:')
          print(TEXT)

          def show(bar,height=HEIGHT,width=WIDTH):
              a = np.frombuffer(bar, dtype=np.uint8)
              if len(set(a)) == 1 and a[0] == 255:
                  a[0]=244 #fix for pyplot.imshow that shows black for blank pages.
              a = a.reshape(height,width)
              plt.figure(figsize=(8.5*2,11*2))
              plt.imshow(a,cmap='Greys_r')
              plt.show()

          for i in range(10):
              show(B4.unpack_nibbles(B4.decompress(pages[i])),
                   width=WIDTH,height=HEIGHT)


### Document Container Format:
  
    uint16 width
    uint16 height
    uint16 #pages
    uint32 byte-length of 1st page.
    uint32 byte-length of 2nd page..
        ...
    uint32 0x00000000 <-- index terminator.
    [n-bytes compressed page 1 bitmap]
    [n-bytes compressed page 2 bitmap]
    ...
    [n-bytes compressed last page bitmap]
    [0+ bytes free-form text to EOF]
  
### Compressed Page Format:
Pages are run-length encoded pixel pairs, two pixels per byte.

Byte n = repitition count, if this value is greater than zero, it represents the number of times to repeat the next byte (pixel-pair in byte n+1). If the count is zero, it is a 'raw flag' and the next byte, n+1 then represents a byte-length count for a block of raw pixel pair bytes beginning at byte n+2.
           
Perhaps better explained by the code: 

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

That's it.. easy lifting for a microcontroller. See the attached sample files, one is "The Little Prince" at 500x1000 pixels (as a pure example... I know of no 500x1000 pixle e-ink display), and the other is the first two chapters (which the author released freely a few years ago) of Steven Levy's 'Hackers' -- at 1404x1872 pixels. Looks good on my computer screen, at least... unfortunately I've got perhaps another month to wait on shipping before my e-ink screen arrives... but in the meantime, here's a format and some support code that should work nicely with it when it gets here, or with any othe e-reader project with a 16 shade single-color display and too little computational grunt to handle .PDFs directly.
