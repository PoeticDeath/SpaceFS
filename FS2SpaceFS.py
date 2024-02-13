import os
import win32api
from sys import argv
import win32security as ws
from SpaceFS import SpaceFS, RawDisk

info = (
    ws.OWNER_SECURITY_INFORMATION
    | ws.GROUP_SECURITY_INFORMATION
    | ws.DACL_SECURITY_INFORMATION
)


def get_sec(filename):
    return ws.ConvertSecurityDescriptorToStringSecurityDescriptor(
        ws.GetFileSecurity(filename, info), ws.SDDL_REVISION_1, info
    )


def attrtoATTR(attr):
    ATTR = 0
    for i in [(-2, 32768), (-1, 4096), (-3, 128), (-6, 2048), (-5, 8192), (-11, 1024)]:
        try:
            if attr[i[0]] == "1":
                ATTR += i[1]
        except IndexError:
            pass
    return ATTR


if __name__ == "__main__":
    disk = argv[1]
    path = argv[2]
    sectorsize = int(argv[3])

    i = 0
    while sectorsize > 512:
        i += 1
        sectorsize >>= 1
    RawDisk(open(disk, "rb+"), open(disk, "rb+", buffering=0)).write(
        i.to_bytes(1, "big") + bytes(4) + b"\xff\xfe"
    )
    s = SpaceFS(disk)

    while path[-1] == "\\":
        path = path[:-1]
    drive = [i for i in os.walk(path)]
    i = 0
    for root, folders, files in drive:
        print(
            str(i)
            + " / "
            + str(len(drive))
            + " - "
            + "0 / "
            + str(len(files))
            + " - "
            + str(i / len(drive) * 100)
            + "% Done.",
            end="\r",
        )
        i += 1
        foldername = root[len(path) :].replace("\\", "/")
        if len(foldername) == 0:
            foldername += "/"
        s.createfile(foldername[1:], 448)
        s.writefile(foldername[1:], 0, get_sec(root).encode())

        s.createfile(foldername, 16877)
        s.winattrs[foldername] = attrtoATTR(bin(win32api.GetFileAttributes(root))[2:])

        if len(foldername) == 1:
            s.createfile(":", 448)
            s.writefile(":", 0, b"SpaceFS")

        o = 0
        for file in files:
            rootfile = root + "\\" + file
            filename = root[len(path) :].replace("\\", "/") + "/" + file
            s.createfile(filename[1:], 448)
            s.writefile(filename[1:], 0, get_sec(rootfile).encode())

            s.createfile(filename, 448)
            s.winattrs[filename] = attrtoATTR(
                bin(win32api.GetFileAttributes(rootfile))[2:]
            )
            try:
                s.writefile(filename, 0, open(rootfile, "rb").read())
            except OSError:
                pass

            o += 1
            print(
                str(i)
                + " / "
                + str(len(drive))
                + " - "
                + str(o)
                + " / "
                + str(len(files))
                + " - "
                + str(i / len(drive) * 100)
                + "% Done.",
                end="\r",
            )

    s.simptable(F=True)
