import struct

def chs_to_sectors(head, byte2, byte3, nh, ns):

	s = byte2 & 0x3f
	c = byte3 + ((byte2 & 0xc0) * 4)

	return (c * nh + head) * ns + (s - 1)

with open('WinXPSP3x86.bin', 'rb') as infile:

	mbr = infile.read(512)
	sig = struct.unpack('H', mbr[510:512])[0]

	if sig != 0xAA55:
		print "**: MBR is missing signature!"

	mbr_offset = 446

	for i in range(0, 4):

		part_rec_raw = mbr[mbr_offset:mbr_offset+16]
		part = struct.unpack('8B2i', part_rec_raw)
		print [hex(x) for x in part]
		
		start_sector = part[8] * 512

		if start_sector > 0:

			print "Starts At           : {0:,} [{0:x}]".format(start_sector)

			if part[4] == 0x07: # NTFS

				infile.seek(start_sector)
				vbr = infile.read(512)
	
				oem_id = struct.unpack('8s', vbr[3:11])[0]

				if oem_id == "NTFS    ":

					print "Found               : NTFS OEM ID"

					sectors_per_track = struct.unpack('H', vbr[0x18:0x1A])[0]
					print "Sectors per Track   : {0:,} [{0:x}]".format(sectors_per_track)
					number_of_heads = struct.unpack('H', vbr[0x1A:0x1C])[0]
					print "Number of Heads     : {0:,} [{0:x}]".format(number_of_heads)
					hidden_sectors = struct.unpack('I', vbr[0x1C:0x20])[0]
					print "Hidden Sectors      : {0:,} [{0:x}]".format(hidden_sectors)
					total_sectors_in_the_volume = struct.unpack('Q', vbr[0x28:0x30])[0]
					print "Total Sectors (vol) : {0:,} [{0:x}]".format(total_sectors_in_the_volume)

					start_sector = chs_to_sectors(part[1], part[2], part[3], number_of_heads, sectors_per_track)
					print "Start Sector (CHS)  : {0:,} [{0:x}]".format(start_sector)
					end_sector = chs_to_sectors(part[5], part[6], part[7], number_of_heads, sectors_per_track)
					print "End Sector (CHS)    : {0:,} [{0:x}]".format(end_sector)
					backup_vbr_offset = (part[8] + part[9] - 1) * 512
					print "Backup VBR (calc'd) : {0:,} [{0:x}]".format(backup_vbr_offset)

					if part[9] - 1 != total_sectors_in_the_volume:
						print "NB: Total sectors in volume should be one less than sectors in partition - it's not!"

					if part[1] == 0xfe and part[2] == 0xff and part[3] == 0xff:
						print "NB: Starting CHS is beyond 1024th cylinder; use LBA."

					if part[5] == 0xfe and part[6] == 0xff and part[7] == 0xff:
						print "NB: Ending CHS is beyond 1024th cylinder; use LBA."
					
					infile.seek(backup_vbr_offset)
					backup_vbr = infile.read(512)

					backup_vbr_oem_id = backup_vbr[3:11]
					if backup_vbr_oem_id != "NTFS    ":
						print "**: Backup VBR missing!"
					else:
						if vbr != backup_vbr:
							print "**: Backup VBR found, but doesn't match VBR!"

			mbr_offset += 16
		
