import os

dirs = []
for i in range(26):
    s = 'Torrent/[moo-shi]_Mushishi_[DVD]/[moo-shi]_Mushishi_-_%d_[DVD]_[3BE3DA10].mkv' % i
    s = os.path.dirname(s)

    parts = s.split('/')

    dirs = [parts[0]]
