# look for patches committed or authored by these people
#PEOPLE = ["tomi.valkeinen@ideasonboard.com", "laurent.pinchart@ideasonboard.com"]
PEOPLE = []

# or look for patches that have files in these directories
PATHS=["drivers/video", "include/video", "include/drm", "arch/arm/mach-omap2/display.c",
       "drivers/gpu/drm", "include/uapi/drm",
       "drivers/media", "include/media", "include/uapi/linux/videodev2.h",
       "include/uapi/linux/media-bus-format",
       ]
PATHS=[]

CATEGORIES={
    "Capture": ( "drivers/media", "include/media" ),
    "Display": ( "drivers/video", "include/video", "include/drm", "drivers/gpu", "include/uapi/drm", "drivers/phy/cadence/phy-cadence-dp.c" ),
    "Audio": ( "sound" ),
    "DMA": ( "drivers/dma", "include/linux/dma" ),
    "Touch": ( "drivers/input/touchscreen" ),
    "DT": ( "arch/arm/boot/dts", "arch/arm64/boot/dts", "Documentation/devicetree" ),
    "TI conf": ( "ti_config_fragments" ),
}

# Range of commits to find carried patches
# E.g. "ti-linux/ti-linux-5.4.y ^v5.4.77 ^ti2020.00"
# TI tree, to find the carried patches (range from stable to head)
#VENDOR="ti-linux/ti-linux-5.4.y ^v5.4.77 ^ti2020.00"
VENDOR="renesas/work ^renesas-geert/master"

# upstream trees, to find if the carried patches are there (ranges)
UPSTREAMS=["renesas/work..v6.9"]

# discard upstreamed commits in these trees
#DROP_UPSTREAMED=UPSTREAMS
#DROP_UPSTREAMED=["ti-linux/ti-linux-5.4.y..v5.10"]
DROP_UPSTREAMED=[]
