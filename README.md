# PDFto4BC

A tool to convert .PDF documents to a paginated four-bit depth packed-pixel run-length encoded format with appended text metadata. Allows for optional cropping and scales to a specified target display's dimensions. The "4bc" format is intended to be easily parsed and decompressed a page at a time by low-power small memory devices (microcontrollers) while still providing reasonably good compression. Created for a DIY e-reader project based on an ESP32 and WaveShare e-ink display (1404x1872, four-bit per pixel).

### Document Format:
  
    uint16 width
    uint16 height
    uint16 #pages
    uint32 byte-length of 1st page.
    uint32 byte-length of 2nd page..
        ...
    uint32 0x00000000 <-- index terminator.
    [n-bytes page 1]
    [n-bytes page 2]
    ...
    [n-bytes last page]
    [0+ bytes free-form text to EOF]
  
### Page Format:
Pages are run-length encoded pixel pairs, two pixels per byte.

Byte n = repitition count, if this value is greater than zero, it represents the number of times to repeat the next byte (pixel-pair in byte n+1). If the count is zero, it is a 'raw flag' and the next byte, n+1 then represents a byte-length count for a block of raw pixel pair bytes beginning at byte n+3.  As there is no termination/division between pages, the decoder should simply continue parsing until height*width pixels, or height*width/2 bytes of packed pixels have been recovered.
           

