import argparse
import os
import struct


def chs_to_sectors(head, byte2, byte3, nh, ns):
    """
    Converts the three CHS bytes from an MPT entry into an LBA value.
    :param head: byte 1 - number of heads
    :param byte2: byte 2 - used to calcualte cylinders and sectors
    :param byte3: byte 3 - used to calcualte cylinders and sectors
    :param nh: Number of Heads
    :param ns: Number of Sectors per Track
    :return:
    """
    s = byte2 & 0x3f
    c = byte3 + ((byte2 & 0xc0) * 4)

    return (c * nh + head) * ns + (s - 1)


class DiskSanity:
    """
    Checks that the partitions specified in the MBR match what's actually present.
    """

    def __init__(self, image, scan):
        """
        Prepare the magic.
        :param image: Path to the disk image.
        :param scan: scan as well as parse?
        """

        self._IMAGE = image
        self._SCAN = scan

        self._LAST_SECTOR = os.path.getsize(self._IMAGE) / 512 - 1

        print "File Size in Bytes  : {0:,} [{0:x}]".format(os.path.getsize(self._IMAGE))
        print "File Size in Sectors: {0:,} [{0:x}]".format(self._LAST_SECTOR + 1)
        if os.path.getsize(self._IMAGE) / float(512) > self._LAST_SECTOR + 1:
            print "**: File size is not a multiple of 512!"

    def parse_ntfs(self, part, infile, start_offset):
        """
        Parse the data from the NTFS partition.
        :param start_offset: Sector at which NTFS VBR is expected.
        :return:
        """
        
        __NTFS_JmpBPB = "\xEB\x52\x90"
        __NTFS_Code_WinXP = "\xFA\x33\xC0\x8E\xD0\xBC\x00\x7C\xFB\xB8\xC0\x07\x8E\xD8\xE8\x16\x00\xB8\x00\x0D\x8E\xC0\x33\xDB\xC6\x06\x0E\x00\x10\xE8\x53\x00\x68\x00\x0D\x68\x6A\x02\xCB"
        __NTFS_Code_Win10 = "\xFA\x33\xC0\x8E\xD0\xBC\x00\x7C\xFB\x68\xC0\x07\x1F\x1E\x68\x66\x00\xCB\x88\x16\x0E\x00\x66\x81\x3E\x03\x00\x4E\x54\x46\x53\x75\x15\xB4\x41\xBB\xAA\x55\xCD"

        infile.seek(start_offset)
        vbr = infile.read(512)

        if vbr[0:3] == __NTFS_JmpBPB:
            print "++: Found NTFS BPB jump code."
        else:
            print "**: NTFS BPB jmup code missing!"

        if vbr[3:11] == 'NTFS    ':
            print "++: Found NTFS OEM ID."
        else:
            print "**: NTFS OEM ID missing!"

        if vbr[0x54:0x7B] == __NTFS_Code_WinXP:
            print "++: Found WinXP NTFS boot code."
        elif vbr[0x54:0x7B] == __NTFS_Code_Win10:
            print "++: Found Win10 NTFS boot code."
        else:
            print "**: NTFS boot code missing or unrecognised!"

        sectors_per_track = struct.unpack('H', vbr[0x18:0x1A])[0]
        print "Sectors per Track   : {0:,} [{0:x}]".format(sectors_per_track)
        number_of_heads = struct.unpack('H', vbr[0x1A:0x1C])[0]
        print "Number of Heads     : {0:,} [{0:x}]".format(number_of_heads)
        hidden_sectors = struct.unpack('I', vbr[0x1C:0x20])[0]
        print "Hidden Sectors      : {0:,} [{0:x}]".format(hidden_sectors)
        total_sectors_in_the_volume = struct.unpack('Q', vbr[0x28:0x30])[0]
        print "Total Sectors (vol) : {0:,} [{0:x}]".format(total_sectors_in_the_volume)

        if not part is None:
            start_offset = chs_to_sectors(part[1], part[2], part[3], number_of_heads, sectors_per_track)
            print "Start Sector (CHS)  : {0:,} [{0:x}]".format(start_offset)
            end_sector = chs_to_sectors(part[5], part[6], part[7], number_of_heads, sectors_per_track)
            print "End Sector (CHS)    : {0:,} [{0:x}]".format(end_sector)

            if part[9] - 1 != total_sectors_in_the_volume:
                print "NB: Total sectors in volume should be one less than sectors in partition - it's not!"

            if part[8] != hidden_sectors:
                print "**: Hidden sectors should equal starting LBA - it doesn't!", part[8], total_sectors_in_the_volume

            if part[1] == 0xfe and part[2] == 0xff and part[3] == 0xff:
                print "NB: Starting CHS is beyond 1024th cylinder; use LBA."

            if part[5] == 0xfe and part[6] == 0xff and part[7] == 0xff:
                print "NB: Ending CHS is beyond 1024th cylinder; use LBA."

        backup_vbr_offset = hidden_sectors + total_sectors_in_the_volume
        print "Backup VBR Sector   : {0:,} [{0:x}]".format(backup_vbr_offset)

        if backup_vbr_offset / 512 > self._LAST_SECTOR:
            print "**: Backup VBR offset is beyond end of input!"
        else:
            infile.seek(backup_vbr_offset)
            backup_vbr = infile.read(512)
            backup_vbr_oem_id = backup_vbr[3:11]
            if backup_vbr_oem_id != "NTFS    ":
                print "**: Backup VBR missing!"
            else:
                if vbr != backup_vbr:
                    print "**: Backup VBR found, but doesn't match VBR!"

    def check_sanity(self):
        """
        Conduct the magic.
        """

        with open(self._IMAGE, 'rb') as infile:
            mbr = infile.read(512)
            sig = struct.unpack('H', mbr[510:512])[0]

            if sig != 0xAA55:
                print "**: MBR signature is missing!"

            mbr_offset = 446

            for i in range(0, 4):

                part_rec_raw = mbr[mbr_offset:mbr_offset + 16]
                part = struct.unpack('8B2i', part_rec_raw)
                print "MPT#{0}: {1}".format(i+1, [hex(x) for x in part])

                start_offset = part[8] * 512

                if start_offset > 0:

                    print "Starts At           : {0:,} [{0:x}]".format(start_offset)

                    if part[4] == 0x07:  # NTFS

                        if start_offset / 512 > self._LAST_SECTOR:
                            print "**: Starting sector is beyond end of input!"
                        else:
                            self.parse_ntfs(part, infile, start_offset)

                    elif part[4] == 0xEE: # Protective MBR

                        print "**: Warning! Protective MBR entry found! Is this a GPT disk??"

                mbr_offset += 16

            if self._SCAN:
                self.scan(infile)

    def scan(self, infile):
        """

        :param infile: file handle to scan
        """
        print "Starting scan..."
        for i in xrange(0, self._LAST_SECTOR):
            infile.seek(i * 512 + 3)
            if infile.read(8) == 'NTFS    ':
                print "Found NTFS OEM ID at sector {0:,} [{0:x}]. Checking...".format(i)
                self.parse_ntfs(None, infile, i * 512)
        print "Scan finished."


if __name__ == '__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument('disk', help="Path to disk image. E.g. '/path/to/file.dd' or '/dev/sdb'.")
    argparser.add_argument('--scan', help="Scan the image for partitions/volumes.", action='store_true')
    args = argparser.parse_args()

    ds = DiskSanity(args.disk, args.scan)
    ds.check_sanity()
